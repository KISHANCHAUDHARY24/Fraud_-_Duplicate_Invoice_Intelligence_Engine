from rest_framework import serializers

from .models import Approval, Payment


class ApprovalSerializer(serializers.ModelSerializer):
    """An approval step with enough invoice context for the approval queue."""

    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    vendor_name = serializers.CharField(source="invoice.vendor.vendor_name", read_only=True)
    amount = serializers.DecimalField(source="invoice.amount", max_digits=14, decimal_places=2, read_only=True)
    currency = serializers.CharField(source="invoice.currency", read_only=True)
    risk_score = serializers.IntegerField(source="invoice.risk_score", read_only=True)
    risk_level = serializers.CharField(source="invoice.risk_level", read_only=True)
    invoice_status = serializers.CharField(source="invoice.approval_status", read_only=True)
    submitted_by_name = serializers.CharField(source="invoice.submitted_by.__str__", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()
    level_label = serializers.CharField(source="get_level_display", read_only=True)
    decision_label = serializers.CharField(source="get_decision_display", read_only=True)

    class Meta:
        model = Approval
        fields = ("id", "invoice", "invoice_number", "vendor_name", "amount", "currency", "risk_score", "risk_level",
                  "invoice_status", "submitted_by_name", "level", "level_label", "decision", "decision_label",
                  "assigned_to", "assigned_to_name", "decided_by", "decided_by_name", "comment", "created_at",
                  "decided_at")
        read_only_fields = fields

    def get_assigned_to_name(self, approval):
        return str(approval.assigned_to) if approval.assigned_to_id else None

    def get_decided_by_name(self, approval):
        if approval.decided_by_id:
            return str(approval.decided_by)
        return "System" if approval.decision == Approval.Decision.APPROVED else None


class DecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class RequiredCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, error_messages={"blank": "A comment is required."})


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    vendor_name = serializers.CharField(source="invoice.vendor.vendor_name", read_only=True)
    bank_account = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    note = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ("id", "reference", "invoice", "invoice_number", "vendor_name", "amount", "currency", "bank_account",
                  "status", "status_label", "paid_at", "created_at", "note")
        read_only_fields = fields

    def get_bank_account(self, payment):
        return payment.bank_account.masked_account if payment.bank_account_id else None

    def get_note(self, payment):
        return "Simulated payment for academic demonstration. No money is transferred."
