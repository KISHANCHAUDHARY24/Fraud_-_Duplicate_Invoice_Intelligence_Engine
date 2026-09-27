"""Read-only queries for the fraud investigation page (docs/api.md §2.6)."""

from accounts.capabilities import Cap, user_can
from approvals.serializers import ApprovalSerializer
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from invoices.models import Invoice
from invoices.selectors import visible_invoices
from invoices.serializers import InvoiceDetailSerializer, InvoiceListSerializer
from vendors.selectors import risk_indicators, vendor_dashboard
from vendors.serializers import VendorSerializer

from .models import FraudAlert


def similar_invoices(invoice: Invoice, user) -> list[dict]:
    """
    Duplicate candidates from the latest analysis, with their invoice details.
    Reviewers (Manager / Auditor / Admin) see every candidate: they cannot judge a possible
    duplicate without seeing the invoice it matches. Other users (AP officers) only see
    candidates within their own invoice scope; the rest are omitted, not revealed.
    """
    analysis = invoice.analyses.first()
    if analysis is None:
        return []
    candidates = ((analysis.raw_response or {}).get("duplicate") or {}).get("candidates", [])
    ids = [c["invoice_id"] for c in candidates if c.get("invoice_id")]
    candidates_qs = Invoice.objects.filter(pk__in=ids).select_related("vendor", "submitted_by")
    if not user_can(user, Cap.APPROVALS_VIEW):
        candidates_qs = visible_invoices(user, candidates_qs)
    visible = {inv.pk: inv for inv in candidates_qs}
    return [
        {"score": c["score"], "components": c["components"], "invoice": InvoiceListSerializer(visible[c["invoice_id"]]).data,
         "description": visible[c["invoice_id"]].description}
        for c in candidates if c.get("invoice_id") in visible
    ]


def investigation(alert: FraudAlert, user) -> dict:
    invoice = alert.invoice
    vendor = invoice.vendor
    history = visible_invoices(user, vendor.invoices.exclude(pk=invoice.pk).select_related("vendor", "submitted_by"))
    return {
        "alert": alert,
        "invoice": InvoiceDetailSerializer(invoice).data,
        "vendor": {**VendorSerializer(vendor).data, **{k: v for k, v in vendor_dashboard(vendor).items()
                                                        if k in ("total_invoices", "total_spending", "average_invoice",
                                                                 "alert_count", "open_alert_count")},
                   "risk_indicators": risk_indicators(vendor)},
        "similar_invoices": similar_invoices(invoice, user),
        "vendor_history": InvoiceListSerializer(history.order_by("-submission_date", "-id")[:10], many=True).data,
        "approval_history": ApprovalSerializer(
            invoice.approvals.select_related("assigned_to", "decided_by", "invoice__vendor", "invoice__submitted_by")
            .order_by("created_at", "id"), many=True).data,
        "audit_history": AuditLogSerializer(
            AuditLog.objects.filter(entity_type="invoice", entity_id=str(invoice.pk)).select_related("user")
            .order_by("timestamp", "id"), many=True).data,
    }
