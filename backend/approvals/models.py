import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Approval(models.Model):
    """One review step for an invoice (docs/approval-workflow.md)."""

    class Level(models.TextChoices):
        STANDARD = "STANDARD", "Standard approval"
        MANAGER = "MANAGER", "Manager review"
        AUDITOR = "AUDITOR", "Auditor review"

    class Decision(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED", "Clarification requested"
        ESCALATED = "ESCALATED", "Escalated"

    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, related_name="approvals")
    level = models.CharField(max_length=10, choices=Level.choices)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="assigned_approvals",
        help_text="Empty only for automatic system approvals.",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="decided_approvals",
    )
    decision = models.CharField(max_length=30, choices=Decision.choices, default=Decision.PENDING, db_index=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # id breaks timestamp ties
        indexes = [models.Index(fields=["assigned_to", "decision"], name="approval_queue_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice"], condition=Q(decision="PENDING"),
                name="one_pending_approval_per_invoice",
            ),
        ]

    def __str__(self):
        return f"{self.get_level_display()} of {self.invoice}: {self.decision}"


def _payment_reference():
    return f"SIM-PAY-{uuid.uuid4().hex[:10].upper()}"


class Payment(models.Model):
    """SIMULATED payment for academic demonstration. No real money is ever moved."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        PAID_SIMULATED = "PAID_SIMULATED", "Paid (simulated)"
        BLOCKED = "BLOCKED", "Blocked"

    invoice = models.OneToOneField("invoices.Invoice", on_delete=models.PROTECT, related_name="payment")
    bank_account = models.ForeignKey(
        "vendors.VendorBankAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    reference = models.CharField(max_length=30, unique=True, default=_payment_reference, editable=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # id breaks timestamp ties
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive")]

    def __str__(self):
        return f"{self.reference} {self.amount} {self.currency} ({self.status})"
