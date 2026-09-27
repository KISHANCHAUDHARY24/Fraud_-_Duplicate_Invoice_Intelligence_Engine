from django.apps import AppConfig


class VendorsConfig(AppConfig):
    """Vendors and their bank account history."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "vendors"
    verbose_name = "Vendors"
