from django.apps import AppConfig


class SystemSettingsConfig(AppConfig):
    """Admin-configurable business rules."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "system_settings"
    verbose_name = "System settings"
