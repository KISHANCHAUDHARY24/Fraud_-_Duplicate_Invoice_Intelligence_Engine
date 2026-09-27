from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "vendor", "amount", "currency", "invoice_date",
        "approval_status", "fraud_status", "risk_score", "risk_level", "submitted_by",
    )
    list_filter = ("approval_status", "fraud_status", "risk_level", "purchase_category", "department")
    search_fields = ("invoice_number", "vendor__vendor_name", "description", "purchase_order_number")
    date_hierarchy = "invoice_date"
    list_select_related = ("vendor", "submitted_by")
    raw_id_fields = ("vendor", "submitted_by", "payment_bank_account")
    # Workflow and risk fields are changed only by services, never by hand.
    readonly_fields = ("approval_status", "fraud_status", "risk_score", "risk_level", "created_at", "updated_at")
    inlines = [InvoiceItemInline]
