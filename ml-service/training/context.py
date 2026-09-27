"""
Rebuild, for every historical invoice, the context Django would send at submission
time, then call the SAME build_features() used by the live service.

Only information available BEFORE each invoice is used (vendor averages, counts,
duplicate candidates), so the model never "sees the future" during training.
"""

import math
from bisect import bisect_right
from datetime import date, datetime

import pandas as pd

from schemas.duplicate import DuplicateWeights
from schemas.fraud import AnalysedInvoice, BankContext, HistoryInvoice, RuleConfig, VendorContext
from services.duplicate_detector import compare
from services.feature_engineering import build_features

DUPLICATE_LOOKBACK_DAYS = 180
RECENT_DAYS = 31


class RunningStats:
    """Mean and standard deviation updated one value at a time (Welford's algorithm)."""

    def __init__(self):
        self.count, self.mean, self._m2 = 0, 0.0, 0.0

    def add(self, value: float):
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self._m2 += delta * (value - self.mean)

    @property
    def std(self):
        return math.sqrt(self._m2 / self.count) if self.count >= 2 else None


def _masked(account_id) -> str:
    return f"****{str(account_id)[-4:]}"


def _to_date(value) -> date:
    return value.date() if isinstance(value, (datetime, pd.Timestamp)) else value


class ContextBuilder:
    def __init__(self, vendors: pd.DataFrame, accounts: pd.DataFrame, config: RuleConfig | None = None):
        self.config = config or RuleConfig()
        self.weights = DuplicateWeights()
        self.vendor_created = {int(r.vendor_id): _to_date(r.created_date) for r in vendors.itertuples()}
        self.accounts = {}
        for r in accounts.sort_values("valid_from").itertuples():
            self.accounts.setdefault(int(r.vendor_id), []).append((_to_date(r.valid_from), r.account_id))
        self.history: dict[int, list[HistoryInvoice]] = {}
        self.company = RunningStats()

    def bank_context(self, vendor_id: int, on: date) -> BankContext:
        timeline = self.accounts.get(vendor_id, [])
        position = bisect_right([since for since, _ in timeline], on) - 1
        if position < 0:
            return BankContext()
        since, account = timeline[position]
        previous = timeline[position - 1][1] if position > 0 else None
        return BankContext(current_account_masked=_masked(account), current_account_age_days=(on - since).days,
                           previous_account_masked=_masked(previous) if previous is not None else None)
    

    def vendor_context(self, vendor_id: int, invoice_date: date, submitted_on: date) -> VendorContext:
        past = self.history.get(vendor_id, [])
        amounts = [h.amount for h in past]
        stats = RunningStats()
        for amount in amounts:
            stats.add(amount)
        first_date = min((h.invoice_date for h in past), default=invoice_date)
        months_active = max(1.0, (invoice_date - first_date).days / 30.4)
        previous_date = max((h.invoice_date for h in past), default=None)
        created = self.vendor_created.get(vendor_id, submitted_on)
        return VendorContext(
            vendor_invoice_count=len(past),
            vendor_avg_amount=stats.mean if past else None,
            vendor_std_amount=stats.std,
            company_avg_amount=self.company.mean if self.company.count else None,
            company_std_amount=self.company.std,
            invoices_last_30_days=sum(1 for h in past if 0 <= (invoice_date - h.invoice_date).days <= 30),
            avg_monthly_invoices=len(past) / months_active if past else 0.0,
            days_since_previous_invoice=max(0, (invoice_date - previous_date).days) if previous_date else None,
            vendor_age_days=max(0, (submitted_on - created).days),
        )

    def duplicate_score(self, invoice: AnalysedInvoice, past: list[HistoryInvoice]) -> float:
        candidates = [h for h in past if abs((invoice.invoice_date - h.invoice_date).days) <= DUPLICATE_LOOKBACK_DAYS]
        return max((compare(invoice, c, self.weights).score for c in candidates), default=0)

    def context_for(self, row) -> dict:
        """What Django would send when this invoice is submitted, using only earlier invoices."""
        vendor_id = int(row.vendor_id)
        submitted = row.submission_datetime.to_pydatetime() if isinstance(row.submission_datetime, pd.Timestamp)             else row.submission_datetime
        invoice = AnalysedInvoice(
            id=int(row.invoice_id), invoice_number=str(row.invoice_number), vendor_id=vendor_id,
            vendor_name=str(row.vendor_name), amount=float(row.amount), currency=str(row.currency),
            invoice_date=_to_date(row.invoice_date), description=str(row.description),
            department=str(row.department), submission_datetime=submitted,
        )
        past = self.history.get(vendor_id, [])
        return {
            "invoice": invoice,
            "vendor_context": self.vendor_context(vendor_id, invoice.invoice_date, submitted.date()),
            "bank": self.bank_context(vendor_id, submitted.date()),
            "recent": [h for h in past if abs((invoice.invoice_date - h.invoice_date).days) <= RECENT_DAYS],
            "past": past,
        }

    def record(self, invoice: AnalysedInvoice):
        """Make this invoice visible to later invoices."""
        self.history.setdefault(invoice.vendor_id, []).append(HistoryInvoice(**invoice.model_dump(exclude={"submission_datetime"})))
        self.company.add(invoice.amount)

    def features_for(self, row) -> dict[str, float]:
        context = self.context_for(row)
        invoice = context["invoice"]
        features = build_features(invoice, context["vendor_context"], context["bank"], context["recent"], self.config,
                                  self.duplicate_score(invoice, context["past"]))
        self.record(invoice)
        return features


def build_feature_frame(invoices: pd.DataFrame, vendors: pd.DataFrame, accounts: pd.DataFrame,
                        config: RuleConfig | None = None) -> pd.DataFrame:
    """`invoices` must already be cleaned and sorted by submission time."""
    builder = ContextBuilder(vendors, accounts, config)
    rows = [builder.features_for(row) for row in invoices.itertuples(index=False)]
    features = pd.DataFrame(rows, index=invoices.index)
    return pd.concat([invoices, features], axis=1)
