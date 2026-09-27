from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Strictly read-only: the audit trail can be viewed, never changed."""

    list_display = ("timestamp", "user", "action", "entity_type", "entity_id", "description")
    list_filter = ("action", "entity_type")
    search_fields = ("description", "entity_id", "user__username")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
