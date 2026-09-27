"""
Feature engineering (docs/machine-learning.md §4.2).

build_features() turns one invoice + its context into a flat dict of numbers.
The SAME function is used by the rule engine now, by model training (Phase 7)
and by live prediction, so training and serving can never disagree
("training/serving skew").
"""

import math
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from schemas.fraud import AnalysedInvoice, BankContext, HistoryInvoice, RuleConfig, VendorContext

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MAX_GAP_DAYS = 365
MAX_Z = 10.0  # cap extreme z-scores so one value cannot dominate

FEATURE_NAMES = [
    "log_amount",
    "amount_dev_vendor",
    "amount_dev_company",
    "submission_hour",
    "day_of_week",
    "is_weekend",
    "is_outside_hours",
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "vendor_invoice_frequency",
    "days_since_previous_invoice",
    "duplicate_similarity",
    "threshold_distance",
    "same_day_invoice_count",
    "round_amount_flag",
    "bank_account_changed",
]


@dataclass(frozen=True)
class SubmissionTime:
    local: datetime
    is_working_day: bool
    is_within_hours: bool

    @property
    def label(self):
        return f"{DAY_NAMES[self.local.weekday()]} {self.local:%H:%M}"


def _parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def submission_time(invoice: AnalysedInvoice, config: RuleConfig) -> SubmissionTime:
    """Convert the submission moment to the company's timezone and compare with working time."""
    local = invoice.submission_datetime.astimezone(ZoneInfo(config.timezone))
    start, end = _parse_hhmm(config.working_hours.start), _parse_hhmm(config.working_hours.end)
    return SubmissionTime(
        local=local,
        is_working_day=local.weekday() in config.working_days,
        is_within_hours=start <= local.time() < end,
    )


def z_score(value: float, mean: float | None, std: float | None) -> float:
    """Standard deviations above (+) or below (-) the mean; 0 when statistics are missing."""
    if mean is None or not std:
        return 0.0
    return max(-MAX_Z, min(MAX_Z, (value - mean) / std))


def is_round_amount(amount: float, base: int) -> bool:
    return amount >= base and math.isclose(amount % base, 0, abs_tol=0.005)


def same_day_count(invoice: AnalysedInvoice, history: list[HistoryInvoice]) -> int:
    return sum(1 for other in history if other.id != invoice.id and other.invoice_date == invoice.invoice_date)


def bank_recently_changed(bank: BankContext, config: RuleConfig) -> bool:
    recent_change = (
        bank.previous_account_masked is not None
        and bank.current_account_age_days is not None
        and bank.current_account_age_days <= config.bank_change_window_days
    )
    return recent_change or bank.differs_from_last_paid


def build_features(invoice: AnalysedInvoice, vendor: VendorContext, bank: BankContext,
                   history: list[HistoryInvoice], config: RuleConfig, duplicate_score: float = 0.0) -> dict[str, float]:
    when = submission_time(invoice, config)
    hour = when.local.hour + when.local.minute / 60
    weekday = when.local.weekday()
    gap = vendor.days_since_previous_invoice

    features = {
        "log_amount": math.log1p(invoice.amount),
        "amount_dev_vendor": z_score(invoice.amount, vendor.vendor_avg_amount, vendor.vendor_std_amount),
        "amount_dev_company": z_score(invoice.amount, vendor.company_avg_amount, vendor.company_std_amount),
        "submission_hour": round(hour, 3),
        "day_of_week": weekday,
        "is_weekend": 0 if when.is_working_day else 1,          # "not a configured working day"
        "is_outside_hours": 0 if when.is_within_hours else 1,
        # Cyclical encoding: 23:30 and 00:30 are close in time, so they must be close in feature space.
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "dow_sin": math.sin(2 * math.pi * weekday / 7),
        "dow_cos": math.cos(2 * math.pi * weekday / 7),
        "vendor_invoice_frequency": vendor.invoices_last_30_days,
        "days_since_previous_invoice": MAX_GAP_DAYS if gap is None else min(gap, MAX_GAP_DAYS),
        "duplicate_similarity": duplicate_score / 100,
        "threshold_distance": (config.approval_threshold - invoice.amount) / config.approval_threshold,
        "same_day_invoice_count": same_day_count(invoice, history),
        "round_amount_flag": 1 if is_round_amount(invoice.amount, config.round_amount_base) else 0,
        "bank_account_changed": 1 if bank_recently_changed(bank, config) else 0,
    }
    return {name: float(features[name]) for name in FEATURE_NAMES}
