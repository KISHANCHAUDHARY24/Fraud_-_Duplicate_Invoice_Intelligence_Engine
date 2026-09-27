from django.contrib import admin

from .models import Vendor, VendorBankAccount


class BankAccountInline(admin.TabularInline):
    """Read-only history. New accounts go through vendors.services.add_bank_account (hash + audit)."""

    model = VendorBankAccount
    extra = 0
    can_delete = False
    fields = ("bank_name", "masked_account", "is_active", "valid_from", "valid_to", "added_by")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("vendor_name", "registration_number", "status", "email", "created_at")
    list_filter = ("status",)
    search_fields = ("vendor_name", "normalized_name", "registration_number", "email")
    readonly_fields = ("normalized_name", "created_at", "updated_at")
    inlines = [BankAccountInline]
