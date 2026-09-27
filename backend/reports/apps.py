from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Dashboard summary, analytics and report exports (read-only; no models)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"
    verbose_name = "Reports"
