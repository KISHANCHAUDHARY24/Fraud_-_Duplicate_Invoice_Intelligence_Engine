from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.capabilities import Cap
from accounts.permissions import ActionCapabilityMixin
from approvals import services as workflow
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from fraud.selectors import similar_invoices

from . import importers, services
from .filters import InvoiceFilter
from .models import Invoice
from .selectors import visible_invoices
from .serializers import InvoiceDetailSerializer, InvoiceListSerializer, InvoiceWriteSerializer


class InvoiceViewSet(ActionCapabilityMixin, viewsets.ModelViewSet):
    """
    /api/invoices/                 GET list (search/filter/sort/paginate), POST create (DRAFT)
    /api/invoices/{id}/            GET detail, PATCH/PUT edit (DRAFT only), DELETE (DRAFT only)
    /api/invoices/{id}/history/    GET audit trail of this invoice
    /api/invoices/{id}/submit/     POST DRAFT -> analysis -> routed (approved / review / blocked)
    /api/invoices/{id}/analyze/    POST run the fraud analysis again
    /api/invoices/{id}/similar/    GET possible duplicates from the latest analysis
    /api/invoices/upload-csv/      POST multipart "file"
    /api/invoices/upload-json/     POST JSON list
    /api/invoices/csv-template/    GET example CSV
    """

    action_capabilities = {
        "list": (Cap.INVOICES_VIEW,),
        "retrieve": (Cap.INVOICES_VIEW,),
        "history": (Cap.INVOICES_VIEW,),
        "create": (Cap.INVOICES_CREATE,),
        "update": (Cap.INVOICES_CREATE,),
        "partial_update": (Cap.INVOICES_CREATE,),
        "destroy": (Cap.INVOICES_CREATE,),
        "upload_csv": (Cap.INVOICES_CREATE,),
        "upload_json": (Cap.INVOICES_CREATE,),
        "csv_template": (Cap.INVOICES_CREATE,),
        "submit": (Cap.INVOICES_SUBMIT,),
        "analyze": (Cap.INVOICES_REANALYZE,),
        "similar": (Cap.INVOICES_VIEW,),
    }
    lookup_value_regex = r"\d+"
    filterset_class = InvoiceFilter
    search_fields = ("invoice_number", "vendor__vendor_name", "description", "purchase_order_number", "department")
    ordering_fields = ("invoice_date", "submission_date", "due_date", "amount", "risk_score",
                       "invoice_number", "vendor__vendor_name", "approval_status", "created_at")
    ordering = ("-submission_date",)

    def get_queryset(self):
        queryset = Invoice.objects.select_related("vendor", "submitted_by", "payment_bank_account")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("items")
        # Object-level security: rows outside the user's scope do not exist for them (404).
        return visible_invoices(self.request.user, queryset)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return InvoiceWriteSerializer
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceListSerializer

    def create(self, request, *args, **kwargs):
        serializer = InvoiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = services.create_invoice(request.user, serializer.validated_data, request=request)
        return Response(InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        invoice = self.get_object()
        serializer = InvoiceWriteSerializer(invoice, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        invoice = services.update_invoice(request.user, invoice, serializer.validated_data, request=request)
        return Response(InvoiceDetailSerializer(invoice).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_invoice(request.user, self.get_object(), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        invoice = self.get_object()  # 404 if not visible
        entries = AuditLog.objects.filter(entity_type="invoice", entity_id=str(invoice.pk)).select_related("user")
        return Response(AuditLogSerializer(entries, many=True).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        invoice = workflow.submit_invoice(self.get_object(), request.user, request)
        return Response(InvoiceDetailSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        invoice = workflow.reanalyze_invoice(self.get_object(), request.user, request)
        return Response(InvoiceDetailSerializer(invoice).data)

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        return Response(similar_invoices(self.get_object(), request.user))

    @action(detail=False, methods=["post"], url_path="upload-csv", parser_classes=[MultiPartParser])
    def upload_csv(self, request):
        rows = importers.read_csv(request.FILES.get("file"))
        result = importers.import_rows(rows, request.user, request=request, first_row_number=2, source="CSV")
        return Response(result, status=status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="upload-json", parser_classes=[JSONParser])
    def upload_json(self, request):
        rows = importers.read_json(request.data)
        result = importers.import_rows(rows, request.user, request=request, first_row_number=1, source="JSON")
        return Response(result, status=status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="csv-template")
    def csv_template(self, request):
        response = HttpResponse(importers.csv_template(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="invoice_import_template.csv"'
        return response
