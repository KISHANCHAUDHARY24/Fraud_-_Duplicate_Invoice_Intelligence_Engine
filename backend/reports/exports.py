"""
The five exportable reports (docs/api.md §2.9). Each one declares who may run it, what the date range
filters on, and its columns; the renderers (renderers.py) turn the rows into CSV or PDF.

Scoping follows the rest of the API: invoice data is limited to visible_invoices(user).
Governance reports (fraud, vendors, audit) need audit access (Admin, Auditor).
Bank accounts only ever appear masked.
"""

from dataclasses import dataclass, field
from typing import Callable

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from accounts.capabilities import Cap
from approvals.models import Approval
from audit.models import AuditLog
from fraud.models import FraudAlert
from invoices.models import Invoice
from invoices.selectors import visible_invoices
from vendors.models import Vendor

from .dashboard import NOT_SPENDING

MAX_ROWS = 10000          # CSV
MAX_PDF_ROWS = 2000       # a PDF longer than this is not readable anyway: use CSV


@dataclass(frozen=True)
class Column:
    header: str
    width: float            # relative width in the PDF
    value: Callable
    pdf: bool = True        # False: CSV only (e.g. long free text)
    align: str = "LEFT"


@dataclass(frozen=True)
class Report:
    key: str
    title: str
    description: str
    date_basis: str
    capability: str
    columns: list = field(default_factory=list)
    rows: Callable = None   # (user, date_from, date_to) -> queryset / list


def _money(value):
    return f"{value:.2f}" if value is not None else ""


def _dt(value):
    """In the active timezone: the export view activates the business timezone setting."""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if value else ""


def _hours(approval):
    if not approval.decided_at:
        return ""
    return f"{(approval.decided_at - approval.created_at).total_seconds() / 3600:.1f}"


# ---------------------------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------------------------
def invoice_rows(user, date_from, date_to):
    return (visible_invoices(user).filter(invoice_date__range=(date_from, date_to))
            .select_related("vendor", "submitted_by").order_by("invoice_date", "id"))


def fraud_rows(user, date_from, date_to):
    return (FraudAlert.objects.filter(invoice__in=visible_invoices(user), created_at__date__range=(date_from, date_to))
            .select_related("invoice__vendor", "assigned_to", "resolved_by", "analysis")
            .prefetch_related("analysis__signals").order_by("created_at", "id"))


def vendor_rows(user, date_from, date_to):
    """One grouped query per figure: annotating several joins (invoices, alerts, accounts) at once
    would multiply the rows and inflate the sums."""
    period = Invoice.objects.filter(invoice_date__range=(date_from, date_to))
    stats = {row["vendor"]: row for row in period.values("vendor").annotate(
        invoices=Count("id"), avg_risk=Avg("risk_score"),
        high_risk=Count("id", filter=Q(risk_level__in=["HIGH", "CRITICAL"])),
        spending=Sum("amount", filter=~Q(approval_status__in=NOT_SPENDING))).order_by()}
    open_alerts = dict(FraudAlert.objects.filter(status__in=FraudAlert.OPEN_STATUSES)
                       .values_list("invoice__vendor").annotate(n=Count("id")).order_by())
    vendors = list(Vendor.objects.prefetch_related("bank_accounts").order_by("vendor_name", "id"))
    for vendor in vendors:
        row = stats.get(vendor.pk, {})
        vendor.period_invoices = row.get("invoices", 0)
        vendor.period_spending = row.get("spending") or 0
        vendor.avg_risk = row.get("avg_risk")
        vendor.high_risk = row.get("high_risk", 0)
        vendor.open_alerts = open_alerts.get(vendor.pk, 0)
        active = [account for account in vendor.bank_accounts.all() if account.is_active]
        vendor.account_since = active[0].valid_from if active else None
    return vendors


def approval_rows(user, date_from, date_to):
    return (Approval.objects.filter(invoice__in=visible_invoices(user), created_at__date__range=(date_from, date_to))
            .select_related("invoice__vendor", "assigned_to", "decided_by").order_by("created_at", "id"))


def audit_rows(user, date_from, date_to):
    return AuditLog.objects.filter(timestamp__date__range=(date_from, date_to)).select_related("user").order_by("timestamp", "id")


def _active_account(vendor):
    active = [account for account in vendor.bank_accounts.all() if account.is_active]
    return f"{active[0].bank_name} {active[0].masked_account}" if active else ""


def _signals(alert):
    return ", ".join(signal.get_signal_type_display() for signal in alert.analysis.signals.all()) if alert.analysis_id else ""


# ---------------------------------------------------------------------------------------------
# definitions
# ---------------------------------------------------------------------------------------------
REPORTS = {report.key: report for report in [
    Report("invoices", "Invoice report", "Every invoice in the period with its status and risk score.",
           "invoice date", Cap.REPORTS_EXPORT, rows=invoice_rows, columns=[
               Column("Invoice", 1.1, lambda i: i.invoice_number),
               Column("Vendor", 1.6, lambda i: i.vendor.vendor_name),
               Column("Invoice date", 0.9, lambda i: i.invoice_date.isoformat()),
               Column("Amount", 0.9, lambda i: _money(i.amount), align="RIGHT"),
               Column("Currency", 0.6, lambda i: i.currency),
               Column("Department", 0.9, lambda i: i.department),
               Column("Category", 0.9, lambda i: i.get_purchase_category_display()),
               Column("Status", 0.9, lambda i: i.get_approval_status_display()),
               Column("Risk score", 0.6, lambda i: "" if i.risk_score is None else i.risk_score, align="RIGHT"),
               Column("Risk level", 0.7, lambda i: i.risk_level or "Not analysed"),
               Column("Fraud review", 1.1, lambda i: i.get_fraud_status_display()),
               Column("Submitted by", 1.0, lambda i: str(i.submitted_by)),
               Column("Submitted at", 1.0, lambda i: _dt(i.submission_date), pdf=False),
               Column("Description", 2.0, lambda i: i.description, pdf=False),
           ]),
    Report("fraud", "Fraud alert report", "Alerts raised in the period, their indicators and the investigation outcome.",
           "date the alert was raised", Cap.AUDIT_VIEW, rows=fraud_rows, columns=[
               Column("Alert", 0.5, lambda a: a.pk, align="RIGHT"),
               Column("Raised", 0.9, lambda a: _dt(a.created_at)),
               Column("Invoice", 1.0, lambda a: a.invoice.invoice_number),
               Column("Vendor", 1.4, lambda a: a.invoice.vendor.vendor_name),
               Column("Amount", 0.8, lambda a: _money(a.invoice.amount), align="RIGHT"),
               Column("Severity", 0.7, lambda a: a.get_severity_display()),
               Column("Score", 0.5, lambda a: a.invoice.risk_score, align="RIGHT"),
               Column("Main indicator", 1.3, lambda a: a.get_primary_type_display()),
               Column("All indicators", 2.0, _signals),
               Column("Status", 0.7, lambda a: a.get_status_display()),
               Column("Assigned to", 1.0, lambda a: str(a.assigned_to) if a.assigned_to_id else ""),
               Column("Outcome", 1.0, lambda a: a.get_outcome_display() if a.outcome else ""),
               Column("Resolved by", 1.0, lambda a: str(a.resolved_by) if a.resolved_by_id else "", pdf=False),
               Column("Resolved at", 1.0, lambda a: _dt(a.resolved_at), pdf=False),
               Column("Resolution note", 2.0, lambda a: a.resolution_note, pdf=False),
           ]),
    Report("vendors", "Vendor risk report", "Each vendor's activity and risk indicators in the period.",
           "invoice date (open alerts are current)", Cap.AUDIT_VIEW, rows=vendor_rows, columns=[
               Column("Vendor", 1.6, lambda v: v.vendor_name),
               Column("Registration no.", 1.0, lambda v: v.registration_number or ""),
               Column("Status", 0.8, lambda v: v.get_status_display()),
               Column("Pays to", 1.3, _active_account),
               Column("Invoices", 0.6, lambda v: v.period_invoices, align="RIGHT"),
               Column("Spending", 0.9, lambda v: _money(v.period_spending or 0), align="RIGHT"),
               Column("Avg. risk", 0.6, lambda v: "" if v.avg_risk is None else f"{v.avg_risk:.1f}", align="RIGHT"),
               Column("High / critical", 0.8, lambda v: v.high_risk, align="RIGHT"),
               Column("Open alerts", 0.7, lambda v: v.open_alerts, align="RIGHT"),
               Column("Account since", 0.9, lambda v: v.account_since.isoformat() if v.account_since else ""),
           ]),
    Report("approvals", "Approval report", "Approval steps opened in the period, who decided and how long it took.",
           "date the step was opened", Cap.REPORTS_EXPORT, rows=approval_rows, columns=[
               Column("Invoice", 1.0, lambda a: a.invoice.invoice_number),
               Column("Vendor", 1.4, lambda a: a.invoice.vendor.vendor_name),
               Column("Amount", 0.8, lambda a: _money(a.invoice.amount), align="RIGHT"),
               Column("Risk", 0.6, lambda a: a.invoice.risk_level or "", align="LEFT"),
               Column("Level", 1.0, lambda a: a.get_level_display()),
               Column("Reviewer", 1.1, lambda a: str(a.assigned_to) if a.assigned_to_id else "Automatic"),
               Column("Opened", 1.0, lambda a: _dt(a.created_at)),
               Column("Decision", 1.0, lambda a: a.get_decision_display()),
               Column("Decided by", 1.1, lambda a: str(a.decided_by) if a.decided_by_id else ("System" if a.decided_at else "")),
               Column("Decided at", 1.0, lambda a: _dt(a.decided_at)),
               Column("Hours", 0.5, _hours, align="RIGHT"),
               Column("Comment", 2.0, lambda a: a.comment, pdf=False),
           ]),
    Report("audit", "Audit log report", "Every recorded action in the period: who, what, on which record and when.",
           "action date", Cap.AUDIT_VIEW, rows=audit_rows, columns=[
               Column("Time", 1.0, lambda e: _dt(e.timestamp)),
               Column("User", 1.1, lambda e: str(e.user) if e.user_id else "System"),
               Column("Action", 1.4, lambda e: e.get_action_display()),
               Column("Record", 0.9, lambda e: f"{e.entity_type} #{e.entity_id}" if e.entity_type else ""),
               Column("Description", 3.4, lambda e: e.description),
               Column("IP address", 0.9, lambda e: e.ip_address or "", pdf=False),
               Column("Old value", 2.0, lambda e: e.old_value or "", pdf=False),
               Column("New value", 2.0, lambda e: e.new_value or "", pdf=False),
           ]),
]}
