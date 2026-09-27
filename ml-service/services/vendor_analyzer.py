"""
Vendor-level indicators (docs/fraud-detection.md §7), shown on the vendor dashboard.
Looks at a vendor's pattern over many invoices rather than at one invoice.
"""

from schemas.fraud import (
    HistoryInvoice, RuleConfig, Severity, Signal, SignalType, VendorAnalysisRequest, VendorAnalysisResponse,
)

from .feature_engineering import is_round_amount
from .rule_engine import SPLIT_MIN_SHARE_OF_THRESHOLD, bank_change_rule, vendor_anomaly_rule

MIN_INVOICES_FOR_PATTERNS = 3
NEAR_THRESHOLD_SHARE = 0.3   # 30% of invoices just below the approval limit is unusual
ROUND_AMOUNT_SHARE = 0.5
MIN_INVOICES_FOR_ROUND_PATTERN = 5


def _near_threshold(amount: float, config: RuleConfig) -> bool:
    return config.approval_threshold * (1 - config.near_threshold_percent / 100) <= amount <= config.approval_threshold


def near_threshold_pattern(invoices: list[HistoryInvoice], config: RuleConfig):
    if len(invoices) < MIN_INVOICES_FOR_PATTERNS:
        return None
    near = [inv for inv in invoices if _near_threshold(inv.amount, config)]
    share = len(near) / len(invoices)
    if share < NEAR_THRESHOLD_SHARE:
        return None
    return Signal(
        type=SignalType.THRESHOLD_PROXIMITY, strength=round(min(1.0, share), 3),
        severity=Severity.MEDIUM if share >= 0.5 else Severity.LOW,
        message=(f"{len(near)} of {len(invoices)} recent invoices ({share:.0%}) are just below the "
                 f"{config.approval_threshold:,.2f} approval threshold"),
        details={"near_threshold_count": len(near), "invoice_count": len(invoices), "share": round(share, 3)},
    )


def split_clusters(invoices: list[HistoryInvoice], config: RuleConfig):
    """Invoices that each have enough other split-sized invoices within the window."""
    low = config.approval_threshold * SPLIT_MIN_SHARE_OF_THRESHOLD
    parts = [inv for inv in invoices if low <= inv.amount <= config.approval_threshold]
    clustered = [
        inv for position, inv in enumerate(parts)
        if sum(1 for other_position, other in enumerate(parts)
               if other_position != position
               and abs((other.invoice_date - inv.invoice_date).days) <= config.split_window_days)
        >= config.split_min_invoices
    ]
    if not clustered:
        return None
    return Signal(
        type=SignalType.SPLIT_PURCHASE, strength=0.8, severity=Severity.MEDIUM,
        message=(f"{len(clustered)} invoices form groups just under the approval threshold within "
                 f"{config.split_window_days} days (possible split purchases)"),
        details={"invoice_ids": sorted(inv.id for inv in clustered if inv.id is not None)},
    )


def round_amount_pattern(invoices: list[HistoryInvoice], config: RuleConfig):
    if len(invoices) < MIN_INVOICES_FOR_ROUND_PATTERN:
        return None
    rounds = sum(1 for inv in invoices if is_round_amount(inv.amount, config.round_amount_base))
    share = rounds / len(invoices)
    if share < ROUND_AMOUNT_SHARE:
        return None
    return Signal(
        type=SignalType.ROUND_AMOUNT, strength=round(share, 3), severity=Severity.INFO,
        message=f"{rounds} of {len(invoices)} recent invoices ({share:.0%}) have round amounts (weak indicator)",
        details={"round_count": rounds, "invoice_count": len(invoices)},
    )


def analyze(request: VendorAnalysisRequest) -> VendorAnalysisResponse:
    config, invoices = request.config, request.recent_invoices
    candidates = [
        bank_change_rule(request.bank, config),
        vendor_anomaly_rule(request.vendor_context),
        near_threshold_pattern(invoices, config),
        split_clusters(invoices, config),
        round_amount_pattern(invoices, config),
    ]
    indicators = sorted((s for s in candidates if s), key=lambda s: s.strength, reverse=True)
    return VendorAnalysisResponse(vendor_id=request.vendor_id, vendor_name=request.vendor_name,
                                  indicators=indicators, indicator_count=len(indicators))
