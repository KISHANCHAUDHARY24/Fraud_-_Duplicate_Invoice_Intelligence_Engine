from django_filters import rest_framework as filters
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.capabilities import Cap
from accounts.models import User
from accounts.permissions import ActionCapabilityMixin, HasCapability
from approvals import services as workflow
from invoices.filters import CharInFilter
from invoices.selectors import visible_invoices

from . import services
from .models import FraudAlert, FraudAnalysis
from .selectors import investigation
from .serializers import AssignAlertSerializer, FraudAlertSerializer, FraudAnalysisSerializer, ResolveAlertSerializer


class FraudAlertFilter(filters.FilterSet):
    severity = CharInFilter(field_name="severity")
    status = CharInFilter(field_name="status")
    primary_type = CharInFilter(field_name="primary_type")
    # "type" matches ANY signal of the analysis that raised the alert, not only the main one.
    type = CharInFilter(field_name="analysis__signals__signal_type", distinct=True)
    assigned_to = filters.NumberFilter(field_name="assigned_to_id")
    vendor = filters.NumberFilter(field_name="invoice__vendor_id")
    invoice = filters.NumberFilter(field_name="invoice_id")
    date_from = filters.DateFilter(field_name="created_at__date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at__date", lookup_expr="lte")

    class Meta:
        model = FraudAlert
        fields = []


class FraudAlertViewSet(ActionCapabilityMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """
    /api/fraud/alerts/?severity=HIGH,CRITICAL&type=DUPLICATE&status=OPEN
    /api/fraud/alerts/{id}/                 full investigation payload
    /api/fraud/alerts/{id}/assign/          {auditor}
    /api/fraud/alerts/{id}/mark-reviewed/
    /api/fraud/alerts/{id}/resolve/         {outcome: CLEARED | CONFIRMED_ISSUE, note}
    /api/fraud/alerts/auditors/             active auditors who can be assigned
    """

    action_capabilities = {
        "list": (Cap.ALERTS_VIEW,),
        "retrieve": (Cap.ALERTS_VIEW,),
        "assign": (Cap.ALERTS_ASSIGN,),
        "auditors": (Cap.ALERTS_ASSIGN,),
        "mark_reviewed": (Cap.ALERTS_RESOLVE,),
        "resolve": (Cap.ALERTS_RESOLVE,),
    }
    serializer_class = FraudAlertSerializer
    filterset_class = FraudAlertFilter
    search_fields = ("invoice__invoice_number", "invoice__vendor__vendor_name")
    ordering_fields = ("created_at", "severity", "invoice__risk_score", "status")
    ordering = ("-created_at",)
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        # Alerts are visible exactly when their invoice is visible to the user.
        visible = visible_invoices(self.request.user)
        return (FraudAlert.objects.filter(invoice__in=visible)
                .select_related("invoice__vendor", "assigned_to", "resolved_by", "analysis")
                .prefetch_related("analysis__signals"))

    def retrieve(self, request, *args, **kwargs):
        alert = self.get_object()
        payload = investigation(alert, request.user)
        payload["alert"] = FraudAlertSerializer(alert).data
        return Response(payload)

    @action(detail=False, methods=["get"])
    def auditors(self, request):
        """Names for the "Assign to" drop-down. Only id and name: user management stays Admin-only."""
        users = User.objects.filter(is_active=True, role__code="AUDITOR").order_by("first_name", "last_name", "id")
        return Response([{"id": user.pk, "name": str(user)} for user in users])

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        body = AssignAlertSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        alert = services.assign_alert(self.get_object(), body.validated_data["auditor"], request.user, request)
        return Response(FraudAlertSerializer(alert).data)

    @action(detail=True, methods=["post"], url_path="mark-reviewed")
    def mark_reviewed(self, request, pk=None):
        return Response(FraudAlertSerializer(services.mark_reviewed(self.get_object(), request.user, request)).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        body = ResolveAlertSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        alert = workflow.resolve_alert(self.get_object(), request.user, body.validated_data["outcome"],
                                       body.validated_data["note"], request)
        return Response(FraudAlertSerializer(alert).data)


class FraudAnalysisViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Analysis history: /api/fraud/analyses/?invoice={id}"""

    permission_classes = [HasCapability.of(Cap.FRAUD_VIEW)]
    serializer_class = FraudAnalysisSerializer
    filterset_fields = ("invoice", "risk_level")
    ordering = ("-analyzed_at",)

    def get_queryset(self):
        return (FraudAnalysis.objects.filter(invoice__in=visible_invoices(self.request.user))
                .prefetch_related("signals__related_invoice"))
