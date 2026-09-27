from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q

from common.choices import RiskLevel
from common.models import TimeStampedModel


class SignalType(models.TextChoices):
    DUPLICATE = "DUPLICATE", "Possible duplicate"
    AMOUNT_ANOMALY = "AMOUNT_ANOMALY", "Amount anomaly"
    TIME_ANOMALY = "TIME_ANOMALY", "Unusual submission time"
    THRESHOLD_PROXIMITY = "THRESHOLD_PROXIMITY", "Near approval threshold"
    SPLIT_PURCHASE = "SPLIT_PURCHASE", "Potential split purchase"
    BANK_ACCOUNT_CHANGE = "BANK_ACCOUNT_CHANGE", "Bank account change"
    ROUND_AMOUNT = "ROUND_AMOUNT", "Round amount"
    VENDOR_ANOMALY = "VENDOR_ANOMALY", "Vendor anomaly"
    ML_ANOMALY = "ML_ANOMALY", "Machine-learning anomaly"


class FraudAnalysis(models.Model):
    """
    One analysis run for an invoice. Re-analysis creates a new row, so history
    is kept. The complete ML-service response is stored for traceability.
    """

    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, related_name="analyses")
    risk_score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    duplicate_score = models.FloatField(default=0, help_text="Best duplicate similarity, 0-100.")
    anomaly_score = models.FloatField(null=True, blank=True, help_text="Isolation Forest score, 0-1.")
    is_anomaly = models.BooleanField(default=False)
    model_version = models.CharField(max_length=50, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    analyzed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-analyzed_at", "-id"]  # id breaks timestamp ties
        verbose_name_plural = "fraud analyses"
        constraints = [
            models.CheckConstraint(condition=Q(risk_score__lte=100), name="analysis_risk_score_max_100"),
        ]

    def __str__(self):
        return f"Analysis of {self.invoice} - {self.risk_score}/100 {self.risk_level}"


class FraudSignal(models.Model):
    """One explainable reason that contributed to a risk score."""

    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    analysis = models.ForeignKey(FraudAnalysis, on_delete=models.CASCADE, related_name="signals")
    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, related_name="signals")
    signal_type = models.CharField(max_length=30, choices=SignalType.choices, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    points = models.PositiveSmallIntegerField(default=0, help_text="Contribution to the risk score.")
    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    related_invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="related_signals", help_text="Matched invoice for duplicates / split purchases.",
    )

    class Meta:
        ordering = ["-points", "-id"]  # id breaks ties between equal points

    def __str__(self):
        return f"{self.signal_type} (+{self.points}): {self.message}"


class FraudAlert(TimeStampedModel):
    """
    A case for a human to review, raised when an invoice reaches MEDIUM risk
    or higher. Only an auditor sets the outcome. The system never does.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_REVIEW = "IN_REVIEW", "In review"
        RESOLVED = "RESOLVED", "Resolved"
        DISMISSED = "DISMISSED", "Dismissed"

    class Outcome(models.TextChoices):
        CLEARED = "CLEARED", "Cleared - legitimate"
        CONFIRMED_ISSUE = "CONFIRMED_ISSUE", "Issue confirmed"

    OPEN_STATUSES = (Status.OPEN, Status.IN_REVIEW)

    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, related_name="alerts")
    analysis = models.ForeignKey(
        FraudAnalysis, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts",
    )
    primary_type = models.CharField(max_length=30, choices=SignalType.choices, db_index=True)
    severity = models.CharField(max_length=10, choices=RiskLevel.choices, db_index=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_alerts",
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resolved_alerts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # id breaks timestamp ties
        constraints = [
            # At most one active case per invoice.
            models.UniqueConstraint(
                fields=["invoice"], condition=Q(status__in=["OPEN", "IN_REVIEW"]),
                name="one_open_alert_per_invoice",
            ),
            # A resolved alert must record the human decision.
            models.CheckConstraint(
                condition=~Q(status="RESOLVED") | ~Q(outcome=""),
                name="resolved_alert_has_outcome",
            ),
        ]

    def __str__(self):
        return f"{self.get_primary_type_display()} alert on {self.invoice} ({self.status})"
