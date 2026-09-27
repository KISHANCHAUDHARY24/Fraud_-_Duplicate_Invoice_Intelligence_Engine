from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from common.choices import RiskLevel
from common.models import TimeStampedModel


class Invoice(TimeStampedModel):
    class ApprovalStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        PROCESSING = "PROCESSING", "Processing"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        BLOCKED = "BLOCKED", "Blocked"
        PAID = "PAID", "Paid (simulated)"

    class FraudStatus(models.TextChoices):
        NOT_ANALYZED = "NOT_ANALYZED", "Not analysed"
        ANALYSIS_FAILED = "ANALYSIS_FAILED", "Analysis failed"
        NO_ISSUES = "NO_ISSUES", "No issues found"
        FLAGGED = "FLAGGED", "Flagged for review"
        REVIEWED_CLEARED = "REVIEWED_CLEARED", "Reviewed - cleared"
        REVIEWED_CONFIRMED_ISSUE = "REVIEWED_CONFIRMED_ISSUE", "Reviewed - issue confirmed"

    class PurchaseCategory(models.TextChoices):
        SOFTWARE = "SOFTWARE", "Software"
        HARDWARE = "HARDWARE", "Hardware"
        SERVICES = "SERVICES", "Services"
        CONSULTING = "CONSULTING", "Consulting"
        TRAVEL = "TRAVEL", "Travel"
        OFFICE_SUPPLIES = "OFFICE_SUPPLIES", "Office supplies"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        UTILITIES = "UTILITIES", "Utilities"
        MARKETING = "MARKETING", "Marketing"
        OTHER = "OTHER", "Other"

    # Workflow state machine (docs/approval-workflow.md §2). Services must call
    # transition_to(); anything not listed here is rejected.
    ALLOWED_TRANSITIONS = {
        ApprovalStatus.DRAFT: {ApprovalStatus.SUBMITTED},
        ApprovalStatus.SUBMITTED: {ApprovalStatus.PROCESSING},
        ApprovalStatus.PROCESSING: {ApprovalStatus.APPROVED, ApprovalStatus.UNDER_REVIEW, ApprovalStatus.BLOCKED},
        ApprovalStatus.UNDER_REVIEW: {
            ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.DRAFT,
            ApprovalStatus.PROCESSING,  # re-analysis after a failed analysis
        },
        ApprovalStatus.BLOCKED: {ApprovalStatus.UNDER_REVIEW, ApprovalStatus.REJECTED},
        ApprovalStatus.APPROVED: {ApprovalStatus.PAID},
        ApprovalStatus.REJECTED: set(),
        ApprovalStatus.PAID: set(),
    }

    invoice_number = models.CharField(max_length=50, db_index=True)
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField()
    submission_date = models.DateTimeField(
        default=timezone.now, db_index=True,
        help_text="When the invoice was entered into the system (used for unusual-time detection).",
    )
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    description = models.TextField()
    purchase_category = models.CharField(
        max_length=30, choices=PurchaseCategory.choices, default=PurchaseCategory.OTHER,
    )
    purchase_order_number = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_invoices",
    )
    payment_bank_account = models.ForeignKey(
        "vendors.VendorBankAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoices", help_text="Bank account this invoice asks to be paid into.",
    )
    approval_status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT, db_index=True,
    )
    fraud_status = models.CharField(
        max_length=30, choices=FraudStatus.choices, default=FraudStatus.NOT_ANALYZED,
    )
    # Copy of the latest FraudAnalysis, kept here so lists can filter/sort without joins.
    risk_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-submission_date", "-id"]  # id breaks timestamp ties
        constraints = [
            models.UniqueConstraint(fields=["vendor", "invoice_number"], name="unique_invoice_number_per_vendor"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="invoice_amount_positive"),
            models.CheckConstraint(condition=Q(tax__gte=0), name="invoice_tax_not_negative"),
            models.CheckConstraint(
                condition=Q(due_date__isnull=True) | Q(due_date__gte=F("invoice_date")),
                name="invoice_due_date_after_invoice_date",
            ),
            models.CheckConstraint(
                condition=Q(risk_score__isnull=True) | Q(risk_score__lte=100),
                name="invoice_risk_score_max_100",
            ),
        ]
        indexes = [models.Index(fields=["vendor", "invoice_date"], name="invoice_vendor_date_idx")]

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Invoice amount must be greater than zero."
        if self.tax is not None and self.tax < 0:
            errors["tax"] = "Tax cannot be negative."
        if self.invoice_date and self.invoice_date > timezone.localdate():
            errors["invoice_date"] = "Invoice date cannot be in the future."
        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            errors["due_date"] = "Due date cannot be before the invoice date."
        if self.payment_bank_account_id and self.vendor_id and self.payment_bank_account.vendor_id != self.vendor_id:
            errors["payment_bank_account"] = "Bank account does not belong to this vendor."
        if errors:
            raise ValidationError(errors)

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.approval_status, set())

    def transition_to(self, new_status):
        """Change status in memory after checking the state machine. The caller saves."""
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot change invoice status from {self.approval_status} to {new_status}."
            )
        self.approval_status = new_status

    @property
    def is_editable(self):
        return self.approval_status == self.ApprovalStatus.DRAFT

    def __str__(self):
        return f"{self.invoice_number} ({self.vendor})"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="item_unit_price_not_negative"),
        ]

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} x {self.quantity}"
