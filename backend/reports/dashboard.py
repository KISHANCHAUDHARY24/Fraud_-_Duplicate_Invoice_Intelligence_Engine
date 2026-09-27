"""
Dashboard data (docs/frontend.md §6): KPIs, six chart series and the high-risk table,
in one request. Everything is scoped to the invoices the user may see, so each role's
dashboard only counts what that role is allowed to see.
"""

from datetime import date

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.capabilities import Cap, user_can
from approvals.models import Approval
from common.choices import RiskLevel
from fraud.models import FraudAlert, FraudSignal, SignalType
from invoices.models import Invoice
from invoices.selectors import visible_invoices
from invoices.serializers import InvoiceListSerializer

Status = Invoice.ApprovalStatus
MONTHS = 12
NOT_SPENDING = [Status.DRAFT, Status.REJECTED]
ELEVATED = [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
DECISIONS = [Approval.Decision.APPROVED, Approval.Decision.REJECTED,
             Approval.Decision.CLARIFICATION_REQUESTED, Approval.Decision.ESCALATED]


def month_keys(today: date, count: int = MONTHS) -> list[str]:
    """The last `count` months, oldest first: ['2025-10', ..., '2026-09']."""
    year, month = today.year, today.month
    keys = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _first_day(key: str) -> date:
    year, month = key.split("-")
    return date(int(year), int(month), 1)


def _by_month(rows, value_keys):
    """{'2026-09': {...}} from TruncMonth rows."""
    return {row["month"].strftime("%Y-%m"): {k: row[k] for k in value_keys} for row in rows if row["month"]}


def kpis(user, invoices):
    reviewer = user_can(user, Cap.APPROVALS_DECIDE)
    if user.has_role("ADMIN"):
        pending = Approval.objects.filter(decision=Approval.Decision.PENDING).count()
        pending_scope = "all"
    elif reviewer:
        pending = Approval.objects.filter(decision=Approval.Decision.PENDING, assigned_to=user).count()
        pending_scope = "mine"
    else:
        pending = invoices.filter(approval_status=Status.UNDER_REVIEW).count()
        pending_scope = "my_invoices"
    return {
        "total_invoices": invoices.count(),
        "total_spending": invoices.exclude(approval_status__in=NOT_SPENDING).aggregate(total=Sum("amount"))["total"] or 0,
        "suspicious_invoices": invoices.filter(risk_level__in=ELEVATED).count(),
        "possible_duplicates": FraudSignal.objects.filter(invoice__in=invoices, signal_type=SignalType.DUPLICATE)
                                                  .values("invoice").distinct().count(),
        "pending_approvals": pending,
        "pending_approvals_scope": pending_scope,
        "blocked_invoices": invoices.filter(approval_status=Status.BLOCKED).count(),
    }


def monthly_spending(invoices, keys):
    rows = (invoices.exclude(approval_status__in=NOT_SPENDING).filter(invoice_date__gte=_first_day(keys[0]))
            .annotate(month=TruncMonth("invoice_date")).values("month")
            .annotate(total=Sum("amount"), count=Count("id")).order_by())
    data = _by_month(rows, ["total", "count"])
    return [{"month": key, "total": data.get(key, {}).get("total") or 0, "count": data.get(key, {}).get("count", 0)}
            for key in keys]


def alerts_over_time(invoices, keys):
    rows = (FraudAlert.objects.filter(invoice__in=invoices, created_at__date__gte=_first_day(keys[0]))
            .annotate(month=TruncMonth("created_at")).values("month").annotate(count=Count("id")).order_by())
    data = _by_month(rows, ["count"])
    return [{"month": key, "count": data.get(key, {}).get("count", 0)} for key in keys]


def risk_distribution(invoices):
    counts = dict(invoices.exclude(risk_level__isnull=True).values_list("risk_level").annotate(n=Count("id")).order_by())
    rows = [{"level": level, "count": counts.get(level, 0)} for level in RiskLevel.values]
    rows.append({"level": "NOT_ANALYZED", "count": invoices.filter(risk_level__isnull=True).count()})
    return rows


def status_distribution(invoices):
    counts = dict(invoices.values_list("approval_status").annotate(n=Count("id")).order_by())
    return [{"status": status, "label": label, "count": counts.get(status, 0)} for status, label in Status.choices]


def vendor_risk(invoices, limit=8):
    rows = (invoices.exclude(risk_score__isnull=True).values("vendor_id", "vendor__vendor_name")
            .annotate(avg_risk=Avg("risk_score"), invoices=Count("id"),
                      high_risk=Count("id", filter=Q(risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL])))
            .order_by("-avg_risk", "-high_risk", "vendor__vendor_name")[:limit])
    return [{"vendor_id": r["vendor_id"], "vendor_name": r["vendor__vendor_name"], "avg_risk": round(r["avg_risk"], 1),
             "invoices": r["invoices"], "high_risk": r["high_risk"]} for r in rows]


def approval_trends(invoices, keys):
    rows = (Approval.objects.filter(invoice__in=invoices, decision__in=DECISIONS,
                                    decided_at__date__gte=_first_day(keys[0]))
            .annotate(month=TruncMonth("decided_at")).values("month", "decision").annotate(n=Count("id")).order_by())
    table = {key: {decision: 0 for decision in DECISIONS} for key in keys}
    for row in rows:
        key = row["month"].strftime("%Y-%m")
        if key in table:
            table[key][row["decision"]] = row["n"]
    return [{"month": key, **values} for key, values in table.items()]


def high_risk_invoices(invoices, limit=10):
    rows = (invoices.filter(risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL])
            .exclude(approval_status__in=[Status.REJECTED, Status.PAID])
            .select_related("vendor", "submitted_by").order_by("-risk_score", "-submission_date", "-id")[:limit])
    return InvoiceListSerializer(rows, many=True).data


def dashboard_summary(user) -> dict:
    invoices = visible_invoices(user)
    keys = month_keys(timezone.localdate())
    return {
        "kpis": kpis(user, invoices),
        "monthly_spending": monthly_spending(invoices, keys),
        "alerts_over_time": alerts_over_time(invoices, keys),
        "risk_distribution": risk_distribution(invoices),
        "status_distribution": status_distribution(invoices),
        "vendor_risk": vendor_risk(invoices),
        "approval_trends": approval_trends(invoices, keys),
        "high_risk_invoices": high_risk_invoices(invoices),
        "generated_at": timezone.now(),
    }
