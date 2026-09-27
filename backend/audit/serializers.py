from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ("id", "timestamp", "user", "user_name", "action", "action_label", "entity_type",
                  "entity_id", "description", "old_value", "new_value", "ip_address")
        read_only_fields = fields

    def get_user_name(self, entry):
        return str(entry.user) if entry.user_id else "System"
