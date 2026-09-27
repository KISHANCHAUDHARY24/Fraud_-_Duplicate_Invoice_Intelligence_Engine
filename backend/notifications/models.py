from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        HIGH_RISK_INVOICE = "HIGH_RISK_INVOICE", "New high-risk invoice"
        DUPLICATE_DETECTED = "DUPLICATE_DETECTED", "Duplicate detected"
        APPROVAL_REQUIRED = "APPROVAL_REQUIRED", "Approval required"
        INVOICE_APPROVED = "INVOICE_APPROVED", "Invoice approved"
        INVOICE_REJECTED = "INVOICE_REJECTED", "Invoice rejected"
        CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED", "Clarification requested"
        PAYMENT_BLOCKED = "PAYMENT_BLOCKED", "Payment blocked"
        VENDOR_RISK_ALERT = "VENDOR_RISK_ALERT", "Vendor risk alert"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # id breaks timestamp ties
        indexes = [models.Index(fields=["recipient", "is_read"], name="notification_unread_idx")]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
