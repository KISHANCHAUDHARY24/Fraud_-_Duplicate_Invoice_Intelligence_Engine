from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Append-only audit log."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Audit"
