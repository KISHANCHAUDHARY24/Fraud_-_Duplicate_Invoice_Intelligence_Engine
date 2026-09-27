"""Choice sets shared by more than one app."""

from django.db import models


class RiskLevel(models.TextChoices):
    """Risk band derived from the 0-100 score. A risk indicator, not a fraud verdict."""

    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"
