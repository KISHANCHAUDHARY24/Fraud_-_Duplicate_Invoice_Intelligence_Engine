"""
Risk-based routing after analysis (docs/approval-workflow.md §3).

decide() is a pure function: invoice facts + analysis outcome + settings -> where the
invoice goes and why. apply() carries the decision out (status, Approval, payment
hold, notifications, audit).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from accounts.assignment import pick_auditor, pick_manager
from audit.models import AuditLog
from audit.services import log_action
from common.choices import RiskLevel
from invoices.models import Invoice
from notifications.models import Notification
from notifications.services import notify, notify_roles
from system_settings.services import get_setting

from .models import Approval, Payment

Status = Invoice.ApprovalStatus
Level = Approval.Level


@dataclass(frozen=True)
class RouteDecision:
    status: str                 # next invoice status
    approval_level: str | None  # review level to create, if any
    reason: str


def decide(invoice: Invoice, outcome, approval_threshold: Decimal, auto_approve_low_risk: bool) -> RouteDecision:
    if not outcome.ok:
        return RouteDecision(Status.UNDER_REVIEW, Level.MANAGER,
                             "Fraud analysis could not run, so the invoice needs manual review (fail-safe)")
    level = outcome.risk_level
    if level == RiskLevel.CRITICAL:
        return RouteDecision(Status.BLOCKED, None, "Critical risk: payment blocked pending auditor investigation")
    if level == RiskLevel.HIGH:
        return RouteDecision(Status.UNDER_REVIEW, Level.AUDITOR, "High risk: auditor review required")
    if level == RiskLevel.MEDIUM:
        return RouteDecision(Status.UNDER_REVIEW, Level.MANAGER, "Medium risk: manager review required")
    if outcome.ml_skipped:
        # Without the ML signal the score may be too low (docs/risk-scoring.md §9.3): never auto-approve.
        return RouteDecision(Status.UNDER_REVIEW, Level.MANAGER,
                             "ML model unavailable: low rule-based risk, but manual review is required (fail-safe)")
    if invoice.amount > approval_threshold:
        return RouteDecision(Status.UNDER_REVIEW, Level.MANAGER,
                             f"Low risk, but the amount is above the approval threshold ({approval_threshold:,.2f})")
    if auto_approve_low_risk:
        return RouteDecision(Status.APPROVED, None, "Low risk and within the approval threshold: approved automatically")
    return RouteDecision(Status.UNDER_REVIEW, Level.STANDARD, "Low risk: standard approval")


def apply(invoice: Invoice, outcome, actor=None, request=None) -> RouteDecision:
    decision = decide(invoice, outcome, Decimal(str(get_setting("approval_threshold"))),
                      bool(get_setting("auto_approve_low_risk")))
    old_status = invoice.approval_status
    invoice.transition_to(decision.status)
    invoice.save(update_fields=["approval_status", "updated_at"])

    assignee = None
    if decision.approval_level:
        assignee = (pick_auditor(exclude_user=invoice.submitted_by) if decision.approval_level == Level.AUDITOR
                    else pick_manager(invoice.department, exclude_user=invoice.submitted_by))
        Approval.objects.create(invoice=invoice, level=decision.approval_level, assigned_to=assignee)
        if assignee:
            notify([assignee], Notification.Type.APPROVAL_REQUIRED,
                   title=f"Approval required: {invoice.invoice_number}",
                   message=f"{decision.reason}. Amount {invoice.amount:,.2f} {invoice.currency}, "
                           f"vendor {invoice.vendor}.", invoice=invoice)
    elif decision.status == Status.BLOCKED:
        Payment.objects.update_or_create(invoice=invoice, defaults={
            "amount": invoice.amount, "currency": invoice.currency,
            "bank_account": invoice.payment_bank_account, "status": Payment.Status.BLOCKED})
        log_action(AuditLog.Action.INVOICE_BLOCKED, entity=invoice, request=request,
                   description=f"Payment of {invoice.invoice_number} blocked: {decision.reason}")
        notify_roles(["ADMIN", "AUDITOR"], Notification.Type.PAYMENT_BLOCKED,
                     title=f"Payment blocked: {invoice.invoice_number}", message=decision.reason, invoice=invoice)
        notify([invoice.submitted_by], Notification.Type.PAYMENT_BLOCKED,
               title=f"Payment blocked: {invoice.invoice_number}",
               message="The invoice is under investigation. You will be notified of the outcome.", invoice=invoice)
    elif decision.status == Status.APPROVED:
        Approval.objects.create(invoice=invoice, level=Level.STANDARD, decision=Approval.Decision.APPROVED,
                                comment=decision.reason, decided_at=timezone.now())
        Payment.objects.update_or_create(invoice=invoice, defaults={
            "amount": invoice.amount, "currency": invoice.currency,
            "bank_account": invoice.payment_bank_account, "status": Payment.Status.SCHEDULED})
        log_action(AuditLog.Action.INVOICE_APPROVED, entity=invoice, request=request,
                   description=f"{invoice.invoice_number} approved automatically by the system",
                   old_value={"status": old_status}, new_value={"status": decision.status})
        notify([invoice.submitted_by], Notification.Type.INVOICE_APPROVED,
               title=f"Invoice approved: {invoice.invoice_number}", message=decision.reason, invoice=invoice)

    log_action(AuditLog.Action.INVOICE_ROUTED, user=actor, entity=invoice, request=request,
               description=f"{invoice.invoice_number}: {decision.reason}",
               old_value={"status": old_status},
               new_value={"status": decision.status, "review_level": decision.approval_level,
                          "assigned_to": str(assignee) if assignee else None,
                          "risk_level": outcome.risk_level, "analysis_ok": outcome.ok, "ml_skipped": outcome.ml_skipped})
    return decision
