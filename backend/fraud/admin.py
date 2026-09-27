from django.contrib import admin

from .models import FraudAlert, FraudAnalysis, FraudSignal


class ReadOnlyAdminMixin:
    """Analysis results are produced by the ML service; nobody edits them by hand."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class FraudSignalInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = FraudSignal
    fk_name = "analysis"
    extra = 0
    can_delete = False
    fields = ("signal_type", "severity", "points", "message", "related_invoice")


@admin.register(FraudAnalysis)
class FraudAnalysisAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("invoice", "risk_score", "risk_level", "duplicate_score", "anomaly_score", "model_version", "analyzed_at")
    list_filter = ("risk_level", "is_anomaly")
    search_fields = ("invoice__invoice_number",)
    inlines = [FraudSignalInline]


@admin.register(FraudSignal)
class FraudSignalAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("invoice", "signal_type", "severity", "points", "message")
    list_filter = ("signal_type", "severity")
    search_fields = ("invoice__invoice_number", "message")


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ("invoice", "primary_type", "severity", "status", "assigned_to", "outcome", "created_at")
    list_filter = ("status", "severity", "primary_type", "outcome")
    search_fields = ("invoice__invoice_number",)
    raw_id_fields = ("invoice", "analysis", "assigned_to", "resolved_by")
