from django.contrib import admin

from .models import SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    """
    Visible for inspection. Changes should go through the Settings API/page
    (Phase 4/13), which validates each value and writes an audit entry.
    """

    list_display = ("key", "value", "value_type", "updated_by", "updated_at")
    search_fields = ("key", "description")
    readonly_fields = ("key", "value_type", "description", "updated_by", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
