from django.contrib import admin

from .models import Approval, Payment


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("invoice", "level", "assigned_to", "decision", "decided_by", "created_at", "decided_at")
    list_filter = ("level", "decision")
    search_fields = ("invoice__invoice_number",)
    raw_id_fields = ("invoice", "assigned_to", "decided_by")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "invoice", "amount", "currency", "status", "paid_at")
    list_filter = ("status",)
    search_fields = ("reference", "invoice__invoice_number")
    readonly_fields = ("reference", "created_at")
    raw_id_fields = ("invoice", "bank_account")
