"""
Analytics for a date range (docs/api.md §2.9): volume, spending, averages, alerts, duplicate rate,
risk mix, which signals fire most, vendor risk, approval times and spending by department/category.

Invoice figures use the invoice date; alert figures the date the alert was raised; approval figures
the decision date. Everything is limited to the invoices the user may see (visible_invoices).
"""

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from approvals.models import Approval
from common.choices import RiskLevel
from fraud.models import FraudAlert, FraudSignal, SignalType
from invoices.models import Invoice
from invoices.selectors import visible_invoices

from .dashboard import NOT_SPENDING, risk_distribution, vendor_risk
from .params import months_between

Status = Invoice.ApprovalStatus
HIGH_RISK = [RiskLevel.HIGH, RiskLevel.CRITICAL]
DECIDED = Q(decided_at__isnull=False) & ~Q(decision=Approval.Decision.PENDING)
DURATION = ExpressionWrapper(F("decided_at") - F("created_at"), output_field=DurationField())
# A decision recorded before its step was opened (imported or corrected data) would make averages negative.
TIMED = Q(decided_by__isnull=False, decided_at__gte=F("created_at"))


def _hours(duration):
    return round(duration.total_seconds() / 3600, 1) if duration is not None else None


def _percent(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def summary(invoices, alerts, approvals):
    spending = invoices.exclude(approval_status__in=NOT_SPENDING).aggregate(total=Sum("amount"), avg=Avg("amount"), n=Count("id"))
    analysed = invoices.exclude(risk_score__isnull=True)
    analysed_count = analysed.count()
    duplicates = FraudSignal.objects.filter(invoice__in=analysed, signal_type=SignalType.DUPLICATE).values("invoice").distinct().count()
    decided = approvals.filter(DECIDED)
    human = decided.filter(TIMED)
    automatic = decided.filter(decided_by__isnull=True, decision=Approval.Decision.APPROVED).count()
    return {
        "invoice_count": invoices.count(),
        "analysed_count": analysed_count,
        "total_spending": spending["total"] or 0,
        "average_invoice": round(spending["avg"], 2) if spending["avg"] is not None else 0,
        "alert_count": alerts.count(),
        "open_alert_count": alerts.filter(status__in=FraudAlert.OPEN_STATUSES).count(),
        "duplicate_rate": _percent(duplicates, analysed_count),
        "high_risk_rate": _percent(analysed.filter(risk_level__in=HIGH_RISK).count(), analysed_count),
        "average_risk_score": round(analysed.aggregate(avg=Avg("risk_score"))["avg"] or 0, 1),
        "decisions": decided.count(),
        "auto_approval_rate": _percent(automatic, decided.count()),
        "average_decision_hours": _hours(human.aggregate(avg=Avg(DURATION))["avg"]),
    }


def monthly(invoices, alerts, keys):
    spend = {row["month"].strftime("%Y-%m"): row for row in (
        invoices.exclude(approval_status__in=NOT_SPENDING).annotate(month=TruncMonth("invoice_date")).values("month")
        .annotate(total=Sum("amount"), count=Count("id")).order_by())}
    flagged = {row["month"].strftime("%Y-%m"): row["n"] for row in (
        invoices.filter(risk_level__in=HIGH_RISK).annotate(month=TruncMonth("invoice_date")).values("month")
        .annotate(n=Count("id")).order_by())}
    raised = {row["month"].strftime("%Y-%m"): row["n"] for row in (
        alerts.annotate(month=TruncMonth("created_at")).values("month").annotate(n=Count("id")).order_by())}
    return [{"month": key, "total": spend.get(key, {}).get("total") or 0, "count": spend.get(key, {}).get("count", 0),
             "high_risk": flagged.get(key, 0), "alerts": raised.get(key, 0)} for key in keys]


def spending_by(invoices, field, labels=None, limit=10):
    rows = (invoices.exclude(approval_status__in=NOT_SPENDING).values(field)
            .annotate(total=Sum("amount"), count=Count("id")).order_by("-total")[:limit])
    return [{"key": row[field] or "", "label": (labels or {}).get(row[field], row[field] or "Not set"),
             "total": row["total"], "count": row["count"]} for row in rows]


def signal_frequency(invoices):
    labels = dict(SignalType.choices)
    rows = (FraudSignal.objects.filter(invoice__in=invoices).values("signal_type")
            .annotate(invoices=Count("invoice", distinct=True), points=Avg("points")).order_by("-invoices", "signal_type"))
    return [{"type": row["signal_type"], "label": labels.get(row["signal_type"], row["signal_type"]),
             "invoices": row["invoices"], "average_points": round(row["points"] or 0, 1)} for row in rows]


def approval_times(approvals):
    labels = dict(Approval.Level.choices)
    rows = (approvals.filter(DECIDED, TIMED).values("level")
            .annotate(avg=Avg(DURATION), count=Count("id")).order_by("level"))
    return [{"level": row["level"], "label": labels.get(row["level"], row["level"]),
             "average_hours": _hours(row["avg"]), "decisions": row["count"]} for row in rows]


def analytics(user, date_from, date_to) -> dict:
    scope = visible_invoices(user)
    invoices = scope.filter(invoice_date__range=(date_from, date_to))
    alerts = FraudAlert.objects.filter(invoice__in=scope, created_at__date__range=(date_from, date_to))
    approvals = Approval.objects.filter(invoice__in=scope, decided_at__date__range=(date_from, date_to))
    return {
        "range": {"date_from": date_from, "date_to": date_to},
        "summary": summary(invoices, alerts, approvals),
        "monthly": monthly(invoices, alerts, months_between(date_from, date_to)),
        "risk_distribution": risk_distribution(invoices),
        "signal_frequency": signal_frequency(invoices),
        "vendor_risk": vendor_risk(invoices, limit=10),
        "approval_times": approval_times(approvals),
        "department_spending": spending_by(invoices, "department"),
        "category_spending": spending_by(invoices, "purchase_category", dict(Invoice.PurchaseCategory.choices)),
        "generated_at": timezone.now(),
    }
