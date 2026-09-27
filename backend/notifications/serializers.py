from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ("id", "type", "type_label", "title", "message", "invoice", "invoice_number", "is_read", "created_at")
        read_only_fields = fields
