from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.capabilities import Cap
from accounts.permissions import HasCapability
from invoices.filters import CharInFilter

from .models import AuditLog
from .serializers import AuditLogSerializer


ENTITY_LABELS = {"invoice": "Invoice", "vendor": "Vendor", "fraudalert": "Fraud alert", "user": "User",
                 "system_setting": "Setting", "report": "Report export", "vendorbankaccount": "Bank account"}


class AuditLogFilter(filters.FilterSet):
    user = filters.NumberFilter(field_name="user_id")
    action = CharInFilter(field_name="action")
    entity_type = filters.CharFilter(field_name="entity_type")
    entity_id = filters.CharFilter(field_name="entity_id")
    date_from = filters.DateFilter(field_name="timestamp__date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="timestamp__date", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = []


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/audit-logs/?action=INVOICE_APPROVED,INVOICE_REJECTED&date_from=2026-09-01
    Read-only by design: there is no create/update/delete endpoint for the audit trail.
    """

    permission_classes = [HasCapability.of(Cap.AUDIT_VIEW)]
    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    search_fields = ("description", "entity_id", "user__username")
    ordering_fields = ("timestamp", "action", "entity_type")
    ordering = ("-timestamp",)

    @action(detail=False, methods=["get"], pagination_class=None)
    def actions(self, request):
        """Action codes and labels, for the filter drop-down in the UI."""
        return Response([{"value": value, "label": label} for value, label in AuditLog.Action.choices])

    @action(detail=False, methods=["get"], url_path="entity-types", pagination_class=None)
    def entity_types(self, request):
        """Record types that appear in the log. order_by() first: the model's default ordering
        would otherwise be added to SELECT DISTINCT and every row would count as distinct."""
        types = AuditLog.objects.exclude(entity_type="").order_by().values_list("entity_type", flat=True).distinct()
        return Response([{"value": value, "label": ENTITY_LABELS.get(value, value.replace("_", " ").capitalize())}
                         for value in sorted(types)])
