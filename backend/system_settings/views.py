from copy import deepcopy

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.capabilities import Cap
from accounts.permissions import ActionCapabilityMixin

from . import services
from .defaults import DEFAULT_SETTINGS
from .models import SystemSetting
from .validators import validate_setting


class SystemSettingSerializer(serializers.ModelSerializer):
    default = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = ("key", "value", "value_type", "description", "default", "updated_by_name", "updated_at")
        read_only_fields = fields

    def get_default(self, row):
        return DEFAULT_SETTINGS[row.key][0] if row.key in DEFAULT_SETTINGS else None

    def get_updated_by_name(self, row):
        return str(row.updated_by) if row.updated_by_id else None


class SettingValueSerializer(serializers.Serializer):
    value = serializers.JSONField()


class SystemSettingViewSet(ActionCapabilityMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):
    """
    GET   /api/settings/                    all settings (Admin, Manager, Auditor may view)
    GET   /api/settings/{key}/
    PATCH /api/settings/{key}/  {"value": …} Admin only; validated per key; audited
    POST  /api/settings/{key}/reset/        Admin only; restore the default
    """

    action_capabilities = {
        "list": (Cap.SETTINGS_VIEW,),
        "retrieve": (Cap.SETTINGS_VIEW,),
        "partial_update": (Cap.SETTINGS_MANAGE,),
        "reset": (Cap.SETTINGS_MANAGE,),
    }
    serializer_class = SystemSettingSerializer
    lookup_field = "key"
    lookup_value_regex = r"[a-z_]+"
    pagination_class = None
    filter_backends = []

    def get_queryset(self):
        return SystemSetting.objects.filter(key__in=DEFAULT_SETTINGS).select_related("updated_by")

    def partial_update(self, request, key=None):
        row = self.get_object()
        payload = SettingValueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            value = validate_setting(key, payload.validated_data["value"])
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"value": exc.detail})
        row = services.update_setting(request.user, row.key, value, request=request)
        return Response(SystemSettingSerializer(row).data)

    @action(detail=True, methods=["post"])
    def reset(self, request, key=None):
        row = self.get_object()
        row = services.update_setting(request.user, row.key, deepcopy(DEFAULT_SETTINGS[row.key][0]), request=request)
        return Response(SystemSettingSerializer(row).data)
