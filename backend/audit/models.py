from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditLogImmutableError(Exception):
    """Raised on any attempt to change or delete an audit entry."""


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AuditLogImmutableError("Audit log entries cannot be modified.")

    def delete(self):
        raise AuditLogImmutableError("Audit log entries cannot be deleted.")


class AuditLog(models.Model):
    """Append-only record of every important action (docs/database.md §2.12)."""

    class Action(models.TextChoices):
        # Authentication and users
        USER_LOGIN = "USER_LOGIN", "User logged in"
        USER_LOGIN_FAILED = "USER_LOGIN_FAILED", "Login failed"
        USER_LOGOUT = "USER_LOGOUT", "User logged out"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
        USER_CREATED = "USER_CREATED", "User created"
        USER_UPDATED = "USER_UPDATED", "User updated"
        USER_DEACTIVATED = "USER_DEACTIVATED", "User deactivated"
        ROLE_CHANGED = "ROLE_CHANGED", "Role changed"
        # Vendors
        VENDOR_CREATED = "VENDOR_CREATED", "Vendor created"
        VENDOR_UPDATED = "VENDOR_UPDATED", "Vendor modified"
        VENDOR_DELETED = "VENDOR_DELETED", "Vendor deleted"
        VENDOR_BANK_ACCOUNT_ADDED = "VENDOR_BANK_ACCOUNT_ADDED", "Vendor bank account added"
        VENDOR_BANK_ACCOUNT_CHANGED = "VENDOR_BANK_ACCOUNT_CHANGED", "Vendor bank account changed"
        # Invoices
        INVOICE_CREATED = "INVOICE_CREATED", "Invoice created"
        INVOICE_UPLOADED = "INVOICE_UPLOADED", "Invoices uploaded"
        INVOICE_UPDATED = "INVOICE_UPDATED", "Invoice edited"
        INVOICE_DELETED = "INVOICE_DELETED", "Invoice deleted"
        INVOICE_SUBMITTED = "INVOICE_SUBMITTED", "Invoice submitted"
        INVOICE_ROUTED = "INVOICE_ROUTED", "Invoice routed for review"
        # Fraud analysis
        FRAUD_ANALYSIS_EXECUTED = "FRAUD_ANALYSIS_EXECUTED", "Fraud analysis executed"
        FRAUD_ANALYSIS_FAILED = "FRAUD_ANALYSIS_FAILED", "Fraud analysis failed"
        FRAUD_ALERT_CREATED = "FRAUD_ALERT_CREATED", "Fraud alert created"
        ALERT_ASSIGNED = "ALERT_ASSIGNED", "Alert assigned"
        ALERT_REVIEWED = "ALERT_REVIEWED", "Alert marked as reviewed"
        ALERT_RESOLVED = "ALERT_RESOLVED", "Alert resolved"
        # Workflow
        INVOICE_APPROVED = "INVOICE_APPROVED", "Invoice approved"
        INVOICE_REJECTED = "INVOICE_REJECTED", "Invoice rejected"
        CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED", "Clarification requested"
        INVOICE_ESCALATED = "INVOICE_ESCALATED", "Invoice escalated"
        INVOICE_BLOCKED = "INVOICE_BLOCKED", "Invoice blocked"
        PAYMENT_SIMULATED = "PAYMENT_SIMULATED", "Payment simulated"
        # Administration
        SETTINGS_CHANGED = "SETTINGS_CHANGED", "Settings changed"
        REPORT_EXPORTED = "REPORT_EXPORTED", "Report exported"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs", help_text="Empty for actions performed by the system.",
    )
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=50, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    old_value = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    new_value = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp", "-id"]  # id breaks timestamp ties
        indexes = [models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditLogImmutableError("Audit log entries cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditLogImmutableError("Audit log entries cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.action} {self.entity_type}#{self.entity_id}"
