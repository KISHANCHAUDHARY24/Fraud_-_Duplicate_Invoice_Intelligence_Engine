"""
Rule-based fraud indicators (docs/fraud-detection.md §2).

One small function per rule. Each returns a Signal (with strength 0-1, severity,
a plain-English message and the raw numbers in `details`) or None.
Rules never decide that something is fraud; they point a human at it.
"""

from schemas.fraud import (
    AnalysedInvoice, BankContext, HistoryInvoice, RuleCheckRequest, RuleConfig, Severity, Signal, SignalType,
    VendorContext,
)
from utils.similarity import description_similarity

from .feature_engineering import DAY_NAMES, is_round_amount, submission_time

SPLIT_MIN_SHARE_OF_THRESHOLD = 0.5   # split parts are at least half the threshold...
AMOUNT_Z_THRESHOLD = 3.0             # ...amount anomaly starts at 3 standard deviations
MIN_VENDOR_HISTORY = 5               # need this many past invoices for vendor statistics
FREQUENCY_SPIKE_FACTOR = 3           # 3x the normal monthly invoice count
NEW_VENDOR_DAYS = 30


def _money(value: float) -> str:
    return f"{value:,.2f}"


# ---------------------------------------------------------------------------
# R1: routing only (not a risk signal)
# ---------------------------------------------------------------------------
def _days_ago(days: int) -> str:
    """0 -> 'today', 1 -> '1 day ago', 5 -> '5 days ago' (these messages are read by reviewers)."""
    return "today" if days <= 0 else f"{days} day{'s' if days != 1 else ''} ago"


def above_approval_threshold(invoice: AnalysedInvoice, config: RuleConfig) -> bool:
    return invoice.amount > config.approval_threshold


# ---------------------------------------------------------------------------
# R2: possible duplicate (score comes from the duplicate detector)
# ---------------------------------------------------------------------------
def duplicate_rule(score: float, config: RuleConfig, match_id: int | None = None, match_number: str | None = None):
    if score < config.duplicate_threshold:
        return None
    target = f" invoice {match_number}" if match_number else " a previous invoice"
    return Signal(
        type=SignalType.DUPLICATE, strength=min(1.0, score / 100), severity=Severity.HIGH,
        message=f"{round(score)}% similarity with{target}",
        details={"duplicate_score": score, "threshold": config.duplicate_threshold},
        related_invoice_id=match_id,
    )


# ---------------------------------------------------------------------------
# R3: bank account change
# ---------------------------------------------------------------------------
def bank_change_rule(bank: BankContext, config: RuleConfig):
    age = bank.current_account_age_days
    if bank.previous_account_masked and age is not None and age <= config.bank_change_window_days:
        return Signal(
            type=SignalType.BANK_ACCOUNT_CHANGE, strength=1.0, severity=Severity.HIGH,
            message=(f"Vendor bank account changed {_days_ago(age)} "
                     f"({bank.previous_account_masked} → {bank.current_account_masked})"),
            details={"account_age_days": age, "window_days": config.bank_change_window_days,
                     "previous": bank.previous_account_masked, "current": bank.current_account_masked},
        )
    if bank.differs_from_last_paid:
        return Signal(
            type=SignalType.BANK_ACCOUNT_CHANGE, strength=1.0, severity=Severity.HIGH,
            message=(f"Payment account {bank.current_account_masked} differs from the account used on the "
                     f"vendor's previous paid invoice ({bank.last_paid_account_masked})"),
            details={"current": bank.current_account_masked, "last_paid": bank.last_paid_account_masked},
        )
    return None


# ---------------------------------------------------------------------------
# R4: unusual submission time
# ---------------------------------------------------------------------------
def time_rule(invoice: AnalysedInvoice, config: RuleConfig):
    when = submission_time(invoice, config)
    if when.is_working_day and when.is_within_hours:
        return None
    both = not when.is_working_day and not when.is_within_hours
    working_days = ", ".join(DAY_NAMES[d][:3] for d in config.working_days)
    reasons = []
    if not when.is_working_day:
        reasons.append("on a non-working day")
    if not when.is_within_hours:
        reasons.append(f"outside working hours ({config.working_hours.start}–{config.working_hours.end})")
    return Signal(
        type=SignalType.TIME_ANOMALY, strength=1.0 if both else 0.6,
        severity=Severity.MEDIUM if both else Severity.LOW,
        message=f"Submitted {when.label} ({config.timezone}), {' and '.join(reasons)}",
        details={"local_time": when.local.isoformat(), "working_days": working_days,
                 "working_hours": config.working_hours.model_dump(), "timezone": config.timezone},
    )


# ---------------------------------------------------------------------------
# R5: amount just below the approval threshold
# ---------------------------------------------------------------------------
def threshold_proximity_rule(invoice: AnalysedInvoice, config: RuleConfig):
    threshold, band = config.approval_threshold, config.near_threshold_percent
    lower = threshold * (1 - band / 100)
    if not (lower <= invoice.amount <= threshold):
        return None
    gap_percent = (threshold - invoice.amount) / threshold * 100
    strength = max(0.1, 1 - gap_percent / band)  # closer to the threshold = stronger
    return Signal(
        type=SignalType.THRESHOLD_PROXIMITY, strength=round(strength, 3),
        severity=Severity.MEDIUM if strength >= 0.5 else Severity.LOW,
        message=(f"Amount {_money(invoice.amount)} is {gap_percent:.1f}% below the approval threshold "
                 f"({_money(threshold)})"),
        details={"amount": invoice.amount, "threshold": threshold, "gap_percent": round(gap_percent, 2),
                 "band_percent": band},
    )


# ---------------------------------------------------------------------------
# R6: potential split purchase
# ---------------------------------------------------------------------------
def _qualifies_as_split_part(amount: float, threshold: float) -> bool:
    return threshold * SPLIT_MIN_SHARE_OF_THRESHOLD <= amount <= threshold


def split_purchase_rule(invoice: AnalysedInvoice, history: list[HistoryInvoice], config: RuleConfig):
    threshold = config.approval_threshold
    if not _qualifies_as_split_part(invoice.amount, threshold):
        return None
    parts = [
        other for other in history
        if other.id != invoice.id
        and other.currency == invoice.currency
        and abs((other.invoice_date - invoice.invoice_date).days) <= config.split_window_days
        and _qualifies_as_split_part(other.amount, threshold)
    ]
    if len(parts) < config.split_min_invoices:
        return None

    parts.sort(key=lambda other: other.invoice_date)
    group_amounts = [p.amount for p in parts] + [invoice.amount]
    total = sum(group_amounts)
    dates = [p.invoice_date for p in parts] + [invoice.invoice_date]
    span_days = (max(dates) - min(dates)).days
    same_department = bool(invoice.department) and all(p.department.lower() == invoice.department.lower() for p in parts)
    avg_description = sum(description_similarity(invoice.description, p.description) for p in parts) / len(parts)

    strength = 0.6
    strength += 0.15 if same_department else 0
    strength += 0.15 if avg_description >= 0.7 else 0
    strength += 0.10 if total > threshold else 0
    strength = min(1.0, strength)

    amounts_text = " + ".join(_money(amount) for amount in group_amounts)
    return Signal(
        type=SignalType.SPLIT_PURCHASE, strength=round(strength, 3),
        severity=Severity.HIGH if strength >= 0.85 else Severity.MEDIUM,
        message=(f"Potential Split Purchase: {len(group_amounts)} invoices from {invoice.vendor_name} within "
                 f"{span_days} day(s) ({amounts_text} = {_money(total)}), each below the "
                 f"{_money(threshold)} approval threshold"),
        details={"related_invoice_ids": [p.id for p in parts], "total": round(total, 2), "span_days": span_days,
                 "same_department": same_department, "description_similarity": round(avg_description, 3)},
        related_invoice_id=parts[-1].id,
    )


# ---------------------------------------------------------------------------
# R7: round amount (weak indicator)
# ---------------------------------------------------------------------------
def round_amount_rule(invoice: AnalysedInvoice, config: RuleConfig):
    if not is_round_amount(invoice.amount, config.round_amount_base):
        return None
    return Signal(
        type=SignalType.ROUND_AMOUNT, strength=1.0, severity=Severity.INFO,
        message=f"Round amount ({_money(invoice.amount)}). Common in legitimate invoices; weak indicator only",
        details={"amount": invoice.amount, "base": config.round_amount_base},
    )


# ---------------------------------------------------------------------------
# R8: amount far above the vendor's normal
# ---------------------------------------------------------------------------
def amount_anomaly_rule(invoice: AnalysedInvoice, vendor: VendorContext):
    if vendor.vendor_invoice_count >= MIN_VENDOR_HISTORY and vendor.vendor_avg_amount:
        mean, std, scope = vendor.vendor_avg_amount, vendor.vendor_std_amount, "this vendor's"
    elif vendor.company_avg_amount:
        mean, std, scope = vendor.company_avg_amount, vendor.company_std_amount, "the company"
    else:
        return None

    if std and std >= 0.01 * mean:
        # Uncapped z for the human-readable message (the ML feature uses a capped value).
        z = (invoice.amount - mean) / std
        if z <= AMOUNT_Z_THRESHOLD:
            return None
        strength = min(1.0, 0.5 + (z - AMOUNT_Z_THRESHOLD) / 6)   # z=3 -> 0.5, z=6 -> 1.0
        message = f"Amount {_money(invoice.amount)} is {z:.1f}σ above {scope} average ({_money(mean)})"
    else:
        # All previous amounts (almost) identical: std is useless, compare the ratio instead.
        ratio = invoice.amount / mean
        if ratio < 2:
            return None
        z, strength = None, 0.8
        message = f"Amount {_money(invoice.amount)} is {ratio:.1f}x {scope} usual amount ({_money(mean)})"

    return Signal(
        type=SignalType.AMOUNT_ANOMALY, strength=round(strength, 3),
        severity=Severity.HIGH if strength >= 0.8 else Severity.MEDIUM, message=message,
        details={"amount": invoice.amount, "mean": mean, "std": std, "z_score": None if z is None else round(z, 2),
                 "compared_with": "vendor" if scope == "this vendor's" else "company"},
    )


# ---------------------------------------------------------------------------
# R9: vendor anomaly
# ---------------------------------------------------------------------------
def vendor_anomaly_rule(vendor: VendorContext):
    findings = []  # (strength, reason)
    if vendor.confirmed_issue_count:
        findings.append((1.0, f"vendor has {vendor.confirmed_issue_count} previously confirmed issue(s)"))
    if vendor.vendor_status == "UNDER_REVIEW":
        findings.append((0.6, "vendor is under review"))
    if vendor.open_alert_count:
        findings.append((0.6, f"vendor has {vendor.open_alert_count} open alert(s)"))
    if (vendor.avg_monthly_invoices > 0 and vendor.invoices_last_30_days >= 3
            and vendor.invoices_last_30_days >= FREQUENCY_SPIKE_FACTOR * vendor.avg_monthly_invoices):
        findings.append((0.7, f"{vendor.invoices_last_30_days} invoices in the last 30 days "
                              f"(normally {vendor.avg_monthly_invoices:.1f} per month)"))
    if vendor.vendor_age_days is not None and vendor.vendor_age_days < NEW_VENDOR_DAYS:
        findings.append((0.5, f"new vendor (added {_days_ago(vendor.vendor_age_days)})"))
    if not findings:
        return None

    strength = max(s for s, _ in findings)
    reasons = [reason for _, reason in sorted(findings, reverse=True)]
    return Signal(
        type=SignalType.VENDOR_ANOMALY, strength=strength,
        severity=Severity.HIGH if strength >= 0.9 else Severity.MEDIUM if strength >= 0.6 else Severity.LOW,
        message="Vendor risk: " + "; ".join(reasons),
        details={"reasons": reasons, "open_alerts": vendor.open_alert_count,
                 "confirmed_issues": vendor.confirmed_issue_count, "invoices_last_30_days": vendor.invoices_last_30_days},
    )


# ---------------------------------------------------------------------------
# Run all rules
# ---------------------------------------------------------------------------
RULE_NAMES = ["duplicate", "bank_account_change", "unusual_time", "threshold_proximity",
              "split_purchase", "round_amount", "amount_anomaly", "vendor_anomaly"]


def evaluate(request: RuleCheckRequest) -> list[Signal]:
    invoice, config = request.invoice, request.config
    candidates = [
        duplicate_rule(request.duplicate_score, config, request.duplicate_match_id, request.duplicate_match_number),
        bank_change_rule(request.bank, config),
        time_rule(invoice, config),
        threshold_proximity_rule(invoice, config),
        split_purchase_rule(invoice, request.recent_vendor_invoices, config),
        round_amount_rule(invoice, config),
        amount_anomaly_rule(invoice, request.vendor_context),
        vendor_anomaly_rule(request.vendor_context),
    ]
    return [signal for signal in candidates if signal is not None]
