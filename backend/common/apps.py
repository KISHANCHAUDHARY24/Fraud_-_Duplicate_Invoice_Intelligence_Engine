from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Shared utilities: error handling, health check, base permissions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "common"
