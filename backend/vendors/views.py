from django.db.models import Count, Prefetch, Q, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.capabilities import Cap, user_can
from accounts.permissions import ActionCapabilityMixin
from invoices.selectors import visible_invoices
from invoices.serializers import InvoiceListSerializer

from . import services
from .models import Vendor, VendorBankAccount
from .selectors import SPENDING_EXCLUDED, vendor_dashboard
from .serializers import BankAccountCreateSerializer, BankAccountSerializer, VendorSerializer, VendorWriteSerializer


class VendorViewSet(ActionCapabilityMixin, viewsets.ModelViewSet):
    """
    /api/vendors/                      GET list, POST create
    /api/vendors/{id}/                 GET, PATCH/PUT (Admin), DELETE (Admin, only without invoices)
    /api/vendors/{id}/dashboard/       GET totals, alerts, risk indicators, recent invoices, bank history
    /api/vendors/{id}/bank-accounts/   GET masked history, POST new account (Admin)
    """

    action_capabilities = {
        "list": (Cap.VENDORS_VIEW,),
        "retrieve": (Cap.VENDORS_VIEW,),
        "dashboard": (Cap.VENDORS_VIEW,),
        "create": (Cap.VENDORS_CREATE,),
        "update": (Cap.VENDORS_EDIT,),
        "partial_update": (Cap.VENDORS_EDIT,),
        "destroy": (Cap.VENDORS_EDIT,),
        "bank_accounts": (Cap.BANK_ACCOUNTS_VIEW,),
        "add_bank_account": (Cap.BANK_ACCOUNTS_MANAGE,),
    }
    lookup_value_regex = r"\d+"
    filterset_fields = ("status",)
    search_fields = ("vendor_name", "registration_number", "email", "phone")
    ordering_fields = ("vendor_name", "created_at", "invoice_count", "total_spending")
    ordering = ("vendor_name",)

    def get_queryset(self):
        spending = ~Q(invoices__approval_status__in=SPENDING_EXCLUDED)
        return Vendor.objects.annotate(
            invoice_count=Count("invoices", distinct=True),
            total_spending=Sum("invoices__amount", filter=spending),
        ).prefetch_related(
            Prefetch("bank_accounts", queryset=VendorBankAccount.objects.filter(is_active=True), to_attr="active_accounts")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VendorWriteSerializer
        return VendorSerializer

    def create(self, request, *args, **kwargs):
        serializer = VendorWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = services.create_vendor(request.user, request=request, **serializer.validated_data)
        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        vendor = self.get_object()
        serializer = VendorWriteSerializer(vendor, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        vendor = services.update_vendor(request.user, vendor, request=request, **serializer.validated_data)
        return Response(VendorSerializer(vendor).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_vendor(request.user, self.get_object(), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        vendor = self.get_object()
        # Statistics cover all of the vendor's invoices; the invoice LIST respects the user's scope.
        recent = visible_invoices(request.user, vendor.invoices.select_related("vendor", "submitted_by"))
        return Response({
            "vendor": VendorSerializer(vendor).data,
            **vendor_dashboard(vendor),
            "recent_invoices": InvoiceListSerializer(recent.order_by("-submission_date", "-id")[:10], many=True).data,
            # Account history follows the same rule as /bank-accounts/ (the current masked account is on `vendor`).
            "bank_accounts": BankAccountSerializer(vendor.bank_accounts.select_related("added_by"), many=True).data
            if user_can(request.user, Cap.BANK_ACCOUNTS_VIEW) else [],
        })

    @action(detail=True, methods=["get"], url_path="bank-accounts")
    def bank_accounts(self, request, pk=None):
        vendor = self.get_object()
        return Response(BankAccountSerializer(vendor.bank_accounts.select_related("added_by"), many=True).data)

    @bank_accounts.mapping.post
    def add_bank_account(self, request, pk=None):
        vendor = self.get_object()
        serializer = BankAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = services.add_bank_account(vendor, user=request.user, request=request, **serializer.validated_data)
        return Response(BankAccountSerializer(account).data, status=status.HTTP_201_CREATED)
