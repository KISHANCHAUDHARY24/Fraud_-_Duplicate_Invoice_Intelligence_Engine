from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import Cap
from accounts.permissions import ActionCapabilityMixin, HasCapability
from invoices.models import Invoice

from . import services
from .models import Approval, Payment
from .serializers import ApprovalSerializer, DecisionSerializer, PaymentSerializer, RequiredCommentSerializer


class ApprovalViewSet(ActionCapabilityMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/approvals/                              my queue (Admin: every approval). ?decision=PENDING&level=AUDITOR
    /api/approvals/{id}/approve/                 {comment?}
    /api/approvals/{id}/reject/                  {comment}   (required)
    /api/approvals/{id}/request-clarification/   {comment}   (required) -> invoice back to DRAFT
    /api/approvals/{id}/escalate/                {comment}   (Manager -> Auditor)
    """

    action_capabilities = {
        "list": (Cap.APPROVALS_VIEW,),
        "retrieve": (Cap.APPROVALS_VIEW,),
        "approve": (Cap.APPROVALS_DECIDE,),
        "reject": (Cap.APPROVALS_DECIDE,),
        "request_clarification": (Cap.APPROVALS_DECIDE,),
        "escalate": (Cap.APPROVALS_ESCALATE,),
    }
    serializer_class = ApprovalSerializer
    filterset_fields = ("decision", "level", "invoice")
    search_fields = ("invoice__invoice_number", "invoice__vendor__vendor_name")
    ordering_fields = ("created_at", "decided_at", "invoice__risk_score", "invoice__amount")
    ordering = ("-created_at",)
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        queryset = Approval.objects.select_related(
            "invoice__vendor", "invoice__submitted_by", "assigned_to", "decided_by")
        if self.request.user.has_role("ADMIN"):
            return queryset
        return queryset.filter(assigned_to=self.request.user)

    def _respond(self, approval):
        approval.refresh_from_db()
        return Response(ApprovalSerializer(approval).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        body = DecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._respond(services.approve(self.get_object(), request.user, body.validated_data["comment"], request))

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        body = RequiredCommentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._respond(services.reject(self.get_object(), request.user, body.validated_data["comment"], request))

    @action(detail=True, methods=["post"], url_path="request-clarification")
    def request_clarification(self, request, pk=None):
        body = RequiredCommentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._respond(services.request_clarification(self.get_object(), request.user,
                                                            body.validated_data["comment"], request))

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        body = RequiredCommentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        new_approval = services.escalate(self.get_object(), request.user, body.validated_data["comment"], request)
        return Response(ApprovalSerializer(new_approval).data)


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Simulated payments (academic demonstration only)."""

    permission_classes = [HasCapability.of(Cap.PAYMENTS_VIEW)]
    queryset = Payment.objects.select_related("invoice__vendor", "bank_account")
    serializer_class = PaymentSerializer
    filterset_fields = ("status",)
    search_fields = ("reference", "invoice__invoice_number", "invoice__vendor__vendor_name")
    ordering_fields = ("created_at", "paid_at", "amount")
    ordering = ("-created_at",)


class SimulatePaymentView(APIView):
    """POST /api/payments/{invoice_id}/simulate/: APPROVED -> PAID (simulated, no real money)."""

    permission_classes = [IsAuthenticated, HasCapability.of(Cap.PAYMENTS_SIMULATE)]

    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        return Response(PaymentSerializer(services.simulate_payment(invoice, request.user, request)).data)
