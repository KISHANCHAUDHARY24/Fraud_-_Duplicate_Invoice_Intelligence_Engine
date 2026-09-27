"""Read-only queries for the vendor dashboard (docs/api.md §2.4)."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from common.choices import RiskLevel
from common.text import days_ago
from fraud.models import FraudAlert, FraudSignal, SignalType
from invoices.models import Invoice
from system_settings.services import get_setting

# Invoices that represent real spending (drafts and rejected invoices do not).
SPENDING_EXCLUDED = [Invoice.ApprovalStatus.DRAFT, Invoice.ApprovalStatus.REJECTED]


def spending_invoices(vendor):
    return vendor.invoices.exclude(approval_status__in=SPENDING_EXCLUDED)


def risk_indicators(vendor):
    """Plain-language warning signs shown on the vendor dashboard. Indicators, not verdicts."""
    indicators = []
    today = timezone.localdate()

    if vendor.status != vendor.Status.ACTIVE:
        indicators.append(f"Vendor status is {vendor.get_status_display()}")

    accounts = list(vendor.bank_accounts.order_by("-created_at", "-id")[:2])
    window = int(get_setting("bank_change_window_days"))
    if len(accounts) > 1 and accounts[0].is_active:
        days = (today - accounts[0].valid_from).days
        if days <= window:
            indicators.append(f"Bank account changed {days_ago(days)} ({accounts[1].masked_account} → {accounts[0].masked_account})")

    invoices = vendor.invoices.all()
    duplicates = FraudSignal.objects.filter(invoice__vendor=vendor, signal_type=SignalType.DUPLICATE) \
        .values("invoice").distinct().count()
    if duplicates:
        indicators.append(f"{duplicates} possible duplicate invoice(s)")
    splits = FraudSignal.objects.filter(invoice__vendor=vendor, signal_type=SignalType.SPLIT_PURCHASE) \
        .values("invoice").distinct().count()
    if splits:
        indicators.append(f"{splits} invoice(s) flagged as potential split purchases")

    high_risk = invoices.filter(risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL]).count()
    if high_risk:
        indicators.append(f"{high_risk} high or critical risk invoice(s)")

    threshold = Decimal(str(get_setting("approval_threshold")))
    near_pct = Decimal(str(get_setting("near_threshold_percent")))
    submitted = spending_invoices(vendor)
    total = submitted.count()
    if total >= 3:
        near = submitted.filter(amount__gte=threshold * (1 - near_pct / 100), amount__lte=threshold).count()
        if near / total >= 0.3:
            indicators.append(f"{round(100 * near / total)}% of invoices are just below the approval threshold")
    return indicators


def vendor_dashboard(vendor):
    submitted = spending_invoices(vendor)
    totals = submitted.aggregate(total=Sum("amount"), average=Avg("amount"), count=Count("id"))
    alerts = FraudAlert.objects.filter(invoice__vendor=vendor)
    year_ago = timezone.localdate().replace(day=1) - timedelta(days=365)
    monthly = (
        submitted.filter(invoice_date__gte=year_ago)
        .annotate(month=TruncMonth("invoice_date")).values("month")
        .annotate(total=Sum("amount"), count=Count("id")).order_by("month")
    )
    return {
        "total_invoices": vendor.invoices.count(),
        "submitted_invoices": totals["count"],
        "total_spending": totals["total"] or Decimal("0.00"),
        "average_invoice": (totals["average"] or Decimal("0")).quantize(Decimal("0.01")),
        "alert_count": alerts.count(),
        "open_alert_count": alerts.filter(status__in=FraudAlert.OPEN_STATUSES).count(),
        "risk_distribution": _count_by(vendor.invoices.exclude(risk_level__isnull=True), "risk_level"),
        "status_counts": _count_by(vendor.invoices.all(), "approval_status"),
        "risk_indicators": risk_indicators(vendor),
        "monthly_spending": [
            {"month": row["month"].strftime("%Y-%m"), "total": row["total"], "count": row["count"]} for row in monthly
        ],
    }


def _count_by(queryset, field):
    """{"HIGH": 3, "LOW": 10}: one GROUP BY query."""
    return {row[field]: row["n"] for row in queryset.values(field).annotate(n=Count("id")).order_by()}
