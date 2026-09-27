"""
Invoice workflow actions (docs/approval-workflow.md §4-7).

Every action checks the state machine, who may act, and separation of duties, and
writes its audit entry and notifications inside one database transaction.
"""

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from accounts.assignment import pick_auditor
from audit.models import AuditLog
from audit.services import log_action
from common.exceptions import BusinessError
from fraud import services as fraud_services
from fraud.models import FraudAlert
from invoices.models import Invoice
from notifications.models import Notification
from notifications.services import notify, notify_roles

from . import routing
from .models import Approval, Payment

logger = logging.getLogger(__name__)
Status = Invoice.ApprovalStatus


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _transition(invoice: Invoice, new_status: str):
    try:
        invoice.transition_to(new_status)
    except ValidationError:
        raise BusinessError(
            "INVALID_STATE_TRANSITION",
            f"This action is not possible while the invoice is {invoice.get_approval_status_display().lower()}.",
            status_code=status.HTTP_409_CONFLICT,
        )


def _require_comment(comment: str, action: str):
    if not (comment or "").strip():
        raise BusinessError("COMMENT_REQUIRED", f"A comment is required to {action}.", status_code=400)


def _lock_pending(approval: Approval, user) -> tuple[Approval, Invoice]:
    approval = Approval.objects.select_for_update().select_related("invoice").get(pk=approval.pk)
    if approval.decision != Approval.Decision.PENDING:
        raise BusinessError("INVALID_STATE_TRANSITION", "This approval has already been decided.", status_code=409)
    if approval.assigned_to_id != user.pk:
        raise BusinessError("NOT_ASSIGNED", "Only the assigned reviewer can decide on this invoice.", status_code=403)
    invoice = Invoice.objects.select_for_update().get(pk=approval.invoice_id)
    if invoice.submitted_by_id == user.pk:
        raise BusinessError("SELF_APPROVAL", "You cannot review an invoice you submitted.", status_code=403)
    return approval, invoice


def _decide(approval: Approval, user, decision: str, comment: str):
    approval.decision, approval.decided_by, approval.comment = decision, user, comment
    approval.decided_at = timezone.now()
    approval.save(update_fields=["decision", "decided_by", "comment", "decided_at"])


def _schedule_payment(invoice: Invoice):
    Payment.objects.update_or_create(invoice=invoice, defaults={
        "amount": invoice.amount, "currency": invoice.currency,
        "bank_account": invoice.payment_bank_account, "status": Payment.Status.SCHEDULED})


def _log(action, user, invoice, request, description, old_status, new_status, **extra):
    log_action(action, user=user, entity=invoice, request=request, description=description,
               old_value={"status": old_status}, new_value={"status": new_status, **extra})


# ---------------------------------------------------------------------------
# submit / analyse
# ---------------------------------------------------------------------------
def submit_invoice(invoice: Invoice, user, request=None, submitted_at=None) -> Invoice:
    """
    DRAFT -> SUBMITTED -> PROCESSING -> analysis -> routed. The ML call runs outside any transaction.
    `submitted_at` is only for seed_data (a demo needs e.g. a Sunday 02:17 submission); the API never passes it.
    """
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().select_related("vendor").get(pk=invoice.pk)
        old_status = invoice.approval_status
        _transition(invoice, Status.SUBMITTED)
        invoice.submission_date = submitted_at or timezone.now()   # the moment of (re)submission, used for time rules
        _transition(invoice, Status.PROCESSING)
        invoice.save(update_fields=["approval_status", "submission_date", "updated_at"])
        _log(AuditLog.Action.INVOICE_SUBMITTED, user, invoice, request,
             f"{invoice.invoice_number} submitted for analysis", old_status, invoice.approval_status)

    outcome = fraud_services.analyze_invoice(invoice, user=user, request=request)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().select_related("vendor", "submitted_by").get(pk=invoice.pk)
        routing.apply(invoice, outcome, actor=user, request=request)
    invoice.refresh_from_db()
    return invoice


def reanalyze_invoice(invoice: Invoice, user, request=None) -> Invoice:
    """
    Run the analysis again (e.g. after the ML service was down). The new score is stored for
    reviewers. The workflow status only changes for an invoice stuck in PROCESSING.
    """
    if invoice.approval_status == Status.DRAFT:
        raise BusinessError("INVALID_STATE_TRANSITION", "Submit the invoice instead of re-analysing a draft.", status_code=409)
    outcome = fraud_services.analyze_invoice(invoice, user=user, request=request)
    if not outcome.ok:
        raise BusinessError("ML_SERVICE_UNAVAILABLE", outcome.error, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().select_related("vendor", "submitted_by").get(pk=invoice.pk)
        if invoice.approval_status == Status.PROCESSING:
            routing.apply(invoice, outcome, actor=user, request=request)
    invoice.refresh_from_db()
    return invoice


# ---------------------------------------------------------------------------
# reviewer decisions
# ---------------------------------------------------------------------------
@transaction.atomic
def approve(approval: Approval, user, comment: str = "", request=None) -> Approval:
    approval, invoice = _lock_pending(approval, user)
    old_status = invoice.approval_status
    _transition(invoice, Status.APPROVED)
    if invoice.fraud_status == Invoice.FraudStatus.FLAGGED:
        invoice.fraud_status = Invoice.FraudStatus.REVIEWED_CLEARED   # a human reviewed the flags and accepted them
    invoice.save(update_fields=["approval_status", "fraud_status", "updated_at"])
    _decide(approval, user, Approval.Decision.APPROVED, comment)
    _schedule_payment(invoice)
    fraud_services.close_open_alerts(invoice, user, f"Invoice reviewed and approved by {user}")
    _log(AuditLog.Action.INVOICE_APPROVED, user, invoice, request, f"{invoice.invoice_number} approved by {user}",
         old_status, invoice.approval_status, comment=comment)
    notify([invoice.submitted_by], Notification.Type.INVOICE_APPROVED, title=f"Invoice approved: {invoice.invoice_number}",
           message=comment or f"Approved by {user}.", invoice=invoice)
    return approval


@transaction.atomic
def reject(approval: Approval, user, comment: str, request=None) -> Approval:
    _require_comment(comment, "reject an invoice")
    approval, invoice = _lock_pending(approval, user)
    old_status = invoice.approval_status
    _transition(invoice, Status.REJECTED)
    invoice.save(update_fields=["approval_status", "updated_at"])
    _decide(approval, user, Approval.Decision.REJECTED, comment)
    fraud_services.close_open_alerts(invoice, user, f"Invoice rejected by {user}: {comment}")
    _log(AuditLog.Action.INVOICE_REJECTED, user, invoice, request, f"{invoice.invoice_number} rejected by {user}",
         old_status, invoice.approval_status, comment=comment)
    notify([invoice.submitted_by], Notification.Type.INVOICE_REJECTED, title=f"Invoice rejected: {invoice.invoice_number}",
           message=comment, invoice=invoice)
    return approval


@transaction.atomic
def request_clarification(approval: Approval, user, comment: str, request=None) -> Approval:
    _require_comment(comment, "request clarification")
    approval, invoice = _lock_pending(approval, user)
    old_status = invoice.approval_status
    _transition(invoice, Status.DRAFT)   # back to the submitter, who can edit and resubmit
    invoice.save(update_fields=["approval_status", "updated_at"])
    _decide(approval, user, Approval.Decision.CLARIFICATION_REQUESTED, comment)
    _log(AuditLog.Action.CLARIFICATION_REQUESTED, user, invoice, request,
         f"Clarification requested on {invoice.invoice_number}", old_status, invoice.approval_status, comment=comment)
    notify([invoice.submitted_by], Notification.Type.CLARIFICATION_REQUESTED,
           title=f"Clarification requested: {invoice.invoice_number}", message=comment, invoice=invoice)
    return approval


@transaction.atomic
def escalate(approval: Approval, user, comment: str, request=None) -> Approval:
    _require_comment(comment, "escalate an invoice")
    approval, invoice = _lock_pending(approval, user)
    if approval.level == Approval.Level.AUDITOR:
        raise BusinessError("INVALID_STATE_TRANSITION", "This invoice is already with an auditor.", status_code=409)
    _decide(approval, user, Approval.Decision.ESCALATED, comment)
    auditor = pick_auditor(exclude_user=invoice.submitted_by)
    new_approval = Approval.objects.create(invoice=invoice, level=Approval.Level.AUDITOR, assigned_to=auditor)
    log_action(AuditLog.Action.INVOICE_ESCALATED, user=user, entity=invoice, request=request,
               description=f"{invoice.invoice_number} escalated to auditor {auditor or '(unassigned)'}",
               new_value={"from_level": approval.level, "to": str(auditor) if auditor else None, "comment": comment})
    if auditor:
        notify([auditor], Notification.Type.APPROVAL_REQUIRED, title=f"Escalated to you: {invoice.invoice_number}",
               message=f"Escalated by {user}: {comment}", invoice=invoice)
    return new_approval


# ---------------------------------------------------------------------------
# alert resolution (auditor)
# ---------------------------------------------------------------------------
@transaction.atomic
def resolve_alert(alert: FraudAlert, user, outcome: str, note: str, request=None) -> FraudAlert:
    _require_comment(note, "resolve an alert")
    alert = FraudAlert.objects.select_for_update().select_related("invoice").get(pk=alert.pk)
    if alert.status not in FraudAlert.OPEN_STATUSES:
        raise BusinessError("INVALID_STATE_TRANSITION", "This alert has already been closed.", status_code=409)
    invoice = Invoice.objects.select_for_update().get(pk=alert.invoice_id)
    if invoice.submitted_by_id == user.pk:
        raise BusinessError("SELF_APPROVAL", "You cannot resolve an alert on an invoice you submitted.", status_code=403)

    alert.status, alert.outcome, alert.resolution_note = FraudAlert.Status.RESOLVED, outcome, note
    alert.resolved_by, alert.resolved_at = user, timezone.now()
    alert.save(update_fields=["status", "outcome", "resolution_note", "resolved_by", "resolved_at", "updated_at"])
    old_status = invoice.approval_status

    if outcome == FraudAlert.Outcome.CLEARED:
        invoice.fraud_status = Invoice.FraudStatus.REVIEWED_CLEARED
        if invoice.approval_status == Status.BLOCKED:
            # Unblock: the invoice now needs a normal auditor approval decision.
            _transition(invoice, Status.UNDER_REVIEW)
            reviewer = user if user.has_role("AUDITOR") else pick_auditor(exclude_user=invoice.submitted_by)
            Approval.objects.create(invoice=invoice, level=Approval.Level.AUDITOR, assigned_to=reviewer)
            Payment.objects.filter(invoice=invoice, status=Payment.Status.BLOCKED).delete()
    else:
        invoice.fraud_status = Invoice.FraudStatus.REVIEWED_CONFIRMED_ISSUE
        if invoice.approval_status in (Status.UNDER_REVIEW, Status.BLOCKED):
            _transition(invoice, Status.REJECTED)
            for pending in Approval.objects.filter(invoice=invoice, decision=Approval.Decision.PENDING):
                _decide(pending, user, Approval.Decision.REJECTED, f"Alert confirmed: {note}")
        Payment.objects.filter(invoice=invoice).exclude(status=Payment.Status.PAID_SIMULATED).update(
            status=Payment.Status.BLOCKED)
        notify([invoice.submitted_by], Notification.Type.INVOICE_REJECTED,
               title=f"Invoice rejected after investigation: {invoice.invoice_number}", message=note, invoice=invoice)
        notify_roles(["ADMIN"], Notification.Type.VENDOR_RISK_ALERT,
                     title=f"Issue confirmed on {invoice.invoice_number} ({invoice.vendor})", message=note,
                     invoice=invoice, exclude=user)
    invoice.save(update_fields=["approval_status", "fraud_status", "updated_at"])

    log_action(AuditLog.Action.ALERT_RESOLVED, user=user, entity=alert, request=request,
               description=f"Alert on {invoice.invoice_number} resolved: {alert.get_outcome_display()}",
               old_value={"invoice_status": old_status},
               new_value={"outcome": outcome, "note": note, "invoice_status": invoice.approval_status,
                          "fraud_status": invoice.fraud_status})
    return alert


# ---------------------------------------------------------------------------
# simulated payment
# ---------------------------------------------------------------------------
@transaction.atomic
def simulate_payment(invoice: Invoice, user, request=None) -> Payment:
    """ACADEMIC SIMULATION: records a payment; no money is moved anywhere."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    payment = Payment.objects.filter(invoice=invoice).first()
    if payment and payment.status == Payment.Status.BLOCKED:
        raise BusinessError("PAYMENT_BLOCKED", "This payment is blocked pending investigation.", status_code=409)
    old_status = invoice.approval_status
    _transition(invoice, Status.PAID)
    invoice.save(update_fields=["approval_status", "updated_at"])
    payment, _ = Payment.objects.update_or_create(invoice=invoice, defaults={
        "amount": invoice.amount, "currency": invoice.currency, "bank_account": invoice.payment_bank_account,
        "status": Payment.Status.PAID_SIMULATED, "paid_at": timezone.now()})
    _log(AuditLog.Action.PAYMENT_SIMULATED, user, invoice, request,
         f"Simulated payment {payment.reference} for {invoice.invoice_number}", old_status, invoice.approval_status,
         reference=payment.reference)
    return payment
