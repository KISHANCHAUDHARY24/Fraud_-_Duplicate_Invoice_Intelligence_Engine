from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "description")
    readonly_fields = ("code",)

    def has_add_permission(self, request):
        return False  # the four roles are fixed and created by migration

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "get_full_name", "role", "department", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_superuser", "department")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (("Business role", {"fields": ("role", "department")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Business role", {"fields": ("email", "role", "department")}),
    )
