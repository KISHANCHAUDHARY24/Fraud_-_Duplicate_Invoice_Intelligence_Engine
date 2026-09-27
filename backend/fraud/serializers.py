from rest_framework import serializers

from accounts.models import User

from .models import FraudAlert, FraudAnalysis, FraudSignal


class FraudSignalSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_signal_type_display", read_only=True)
    related_invoice_number = serializers.CharField(source="related_invoice.invoice_number", read_only=True, default=None)

    class Meta:
        model = FraudSignal
        fields = ("id", "signal_type", "label", "severity", "points", "message", "details",
                  "related_invoice", "related_invoice_number")
        read_only_fields = fields


class FraudAnalysisSerializer(serializers.ModelSerializer):
    """One analysis with ready-to-display explanations (taken from the stored ML response)."""

    signals = FraudSignalSerializer(many=True, read_only=True)
    summary = serializers.SerializerMethodField()
    explanation = serializers.SerializerMethodField()
    warnings = serializers.SerializerMethodField()
    anomaly = serializers.SerializerMethodField()
    floor_applied = serializers.SerializerMethodField()
    disclaimer = serializers.SerializerMethodField()

    class Meta:
        model = FraudAnalysis
        fields = ("id", "risk_score", "risk_level", "duplicate_score", "anomaly_score", "is_anomaly",
                  "model_version", "analyzed_at", "summary", "explanation", "warnings", "floor_applied",
                  "anomaly", "signals", "disclaimer")
        read_only_fields = fields

    def _raw(self, analysis, key, default=None):
        return (analysis.raw_response or {}).get(key, default)

    def get_summary(self, analysis):
        return self._raw(analysis, "summary", "")

    def get_explanation(self, analysis):
        return self._raw(analysis, "explanation", [])

    def get_warnings(self, analysis):
        return self._raw(analysis, "warnings", [])

    def get_anomaly(self, analysis):
        return self._raw(analysis, "anomaly")

    def get_floor_applied(self, analysis):
        return (self._raw(analysis, "scoring") or {}).get("floor_applied")

    def get_disclaimer(self, analysis):
        return "Risk indicators require human review. This score is not a determination of fraud."


class FraudAlertSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    vendor = serializers.IntegerField(source="invoice.vendor_id", read_only=True)
    vendor_name = serializers.CharField(source="invoice.vendor.vendor_name", read_only=True)
    amount = serializers.DecimalField(source="invoice.amount", max_digits=14, decimal_places=2, read_only=True)
    risk_score = serializers.IntegerField(source="invoice.risk_score", read_only=True)
    invoice_status = serializers.CharField(source="invoice.approval_status", read_only=True)
    primary_type_label = serializers.CharField(source="get_primary_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    signal_types = serializers.SerializerMethodField()

    class Meta:
        model = FraudAlert
        fields = ("id", "invoice", "invoice_number", "vendor", "vendor_name", "amount", "risk_score", "invoice_status",
                  "primary_type", "primary_type_label", "signal_types", "severity", "status", "status_label",
                  "assigned_to", "assigned_to_name", "outcome", "resolution_note", "resolved_by_name",
                  "resolved_at", "created_at", "updated_at")
        read_only_fields = fields

    def get_assigned_to_name(self, alert):
        return str(alert.assigned_to) if alert.assigned_to_id else None

    def get_resolved_by_name(self, alert):
        return str(alert.resolved_by) if alert.resolved_by_id else None

    def get_signal_types(self, alert):
        return [signal.signal_type for signal in alert.analysis.signals.all()] if alert.analysis_id else []


class AssignAlertSerializer(serializers.Serializer):
    auditor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, role__code="AUDITOR"),
        error_messages={"does_not_exist": "Choose an active auditor."},
    )


class ResolveAlertSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=FraudAlert.Outcome.choices)
    note = serializers.CharField(max_length=2000, error_messages={"blank": "Explain the outcome of your investigation."})
