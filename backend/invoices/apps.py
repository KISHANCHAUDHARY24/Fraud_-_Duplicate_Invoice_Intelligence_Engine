from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    """Invoices, line items and import."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "invoices"
    verbose_name = "Invoices"
