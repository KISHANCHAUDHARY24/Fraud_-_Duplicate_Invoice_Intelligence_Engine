from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from common.models import TimeStampedModel
from common.text import normalize_vendor_name


class Vendor(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        BLOCKED = "BLOCKED", "Blocked"

    vendor_name = models.CharField(max_length=200, db_index=True)
    normalized_name = models.CharField(
        max_length=200, db_index=True, editable=False,
        help_text="Lower-case name without punctuation or legal suffixes; used for fuzzy matching.",
    )
    registration_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        ordering = ["vendor_name"]

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_vendor_name(self.vendor_name)
        # Store "no registration number" as NULL so the unique constraint allows many of them.
        self.registration_number = (self.registration_number or "").strip() or None
        super().save(*args, **kwargs)

    @property
    def active_bank_account(self):
        return self.bank_accounts.filter(is_active=True).first()

    def __str__(self):
        return self.vendor_name


class VendorBankAccount(models.Model):
    """
    A vendor's bank account, kept as history. The full account number is never
    stored: only the last 4 digits (for display) and a keyed HMAC-SHA256 hash
    (to detect whether two accounts are the same). See vendors/services.py.
    """

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="bank_accounts")
    bank_name = models.CharField(max_length=100)
    account_last4 = models.CharField(max_length=4)
    account_hash = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(default=timezone.localdate)
    valid_to = models.DateField(null=True, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="added_bank_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # id breaks timestamp ties
        constraints = [
            models.UniqueConstraint(
                fields=["vendor"], condition=Q(is_active=True),
                name="one_active_bank_account_per_vendor",
            ),
        ]

    @property
    def masked_account(self):
        return f"****{self.account_last4}"

    def __str__(self):
        return f"{self.bank_name} {self.masked_account}"
