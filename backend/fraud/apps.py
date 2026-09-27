from django.apps import AppConfig


class FraudConfig(AppConfig):
    """Fraud analyses, signals and alerts."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "fraud"
    verbose_name = "Fraud"
