import re
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from fraud.serializers import FraudAnalysisSerializer
from vendors.models import Vendor

from .models import Invoice, InvoiceItem

INVOICE_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_/.# ]*$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
MAX_ITEMS = 100


class InvoiceItemSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))

    class Meta:
        model = InvoiceItem
        fields = ("id", "description", "quantity", "unit_price", "line_total")
        read_only_fields = ("id", "line_total")


# ---------------------------------------------------------------------------
# Write: used by the form, CSV import and JSON import (one validation path)
# ---------------------------------------------------------------------------
class InvoiceWriteSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"),
        error_messages={"min_value": "Invoice amount must be greater than zero."},
    )
    tax = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0.00"),
        error_messages={"min_value": "Tax cannot be negative."},
    )
    currency = serializers.CharField(max_length=3, required=False, default="USD")
    items = InvoiceItemSerializer(many=True, required=False)

    class Meta:
        model = Invoice
        fields = ("invoice_number", "vendor", "invoice_date", "due_date", "amount", "currency", "tax",
                  "description", "purchase_category", "purchase_order_number", "department",
                  "payment_bank_account", "items")
        # Uniqueness of (vendor, invoice_number) is checked by the service so it can
        # answer 409 DUPLICATE_INVOICE_NUMBER instead of a generic 400.
        validators = []

    def validate_invoice_number(self, value):
        value = value.strip()
        if not INVOICE_NUMBER_PATTERN.match(value):
            raise serializers.ValidationError("Use letters, digits and - _ / . # only, starting with a letter or digit.")
        return value

    def validate_currency(self, value):
        value = value.strip().upper()
        if not CURRENCY_PATTERN.match(value):
            raise serializers.ValidationError("Currency must be a 3-letter ISO code, e.g. USD, INR, EUR.")
        return value

    def validate_invoice_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Invoice date cannot be in the future.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Description must be at least 3 characters.")
        return value

    def validate_vendor(self, vendor):
        if vendor.status in (Vendor.Status.INACTIVE, Vendor.Status.BLOCKED):
            raise serializers.ValidationError(
                f"Vendor '{vendor}' is {vendor.get_status_display().lower()} and cannot receive invoices."
            )
        return vendor

    def validate_items(self, items):
        if len(items) > MAX_ITEMS:
            raise serializers.ValidationError(f"An invoice can have at most {MAX_ITEMS} line items.")
        return items

    def validate(self, attrs):
        # For PATCH, fall back to the stored values when checking cross-field rules.
        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None) if self.instance else None

        invoice_date, due_date, vendor = current("invoice_date"), current("due_date"), current("vendor")
        if due_date and invoice_date and due_date < invoice_date:
            raise serializers.ValidationError({"due_date": "Due date cannot be before the invoice date."})
        account = attrs.get("payment_bank_account")
        if account and vendor and account.vendor_id != vendor.pk:
            raise serializers.ValidationError({"payment_bank_account": "This bank account does not belong to the vendor."})
        return attrs


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
class InvoiceListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.__str__", read_only=True)
    approval_status_label = serializers.CharField(source="get_approval_status_display", read_only=True)
    risk_level_label = serializers.CharField(source="get_risk_level_display", read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = ("id", "invoice_number", "vendor", "vendor_name", "invoice_date", "submission_date", "due_date",
                  "amount", "currency", "department", "purchase_category", "approval_status",
                  "approval_status_label", "fraud_status", "risk_score", "risk_level", "risk_level_label",
                  "submitted_by", "submitted_by_name", "created_at")
        read_only_fields = fields


class InvoiceDetailSerializer(InvoiceListSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payment_bank_account = serializers.SerializerMethodField()
    latest_analysis = serializers.SerializerMethodField()
    is_editable = serializers.BooleanField(read_only=True)
    fraud_status_label = serializers.CharField(source="get_fraud_status_display", read_only=True)

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + (
            "tax", "description", "purchase_order_number", "payment_bank_account", "fraud_status_label",
            "items", "latest_analysis", "is_editable", "updated_at",
        )
        read_only_fields = fields

    def get_payment_bank_account(self, invoice):
        account = invoice.payment_bank_account
        if account is None:
            return None
        return {"id": account.pk, "bank_name": account.bank_name, "masked_account": account.masked_account,
                "is_active": account.is_active}

    def get_latest_analysis(self, invoice):
        analysis = invoice.analyses.prefetch_related("signals__related_invoice").first()
        return FraudAnalysisSerializer(analysis).data if analysis else None
