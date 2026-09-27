"""Data migration: create the four business roles (reference data every install needs)."""

from django.db import migrations

ROLES = [
    ("ADMIN", "Administrator", "Manages users, vendors, settings; full visibility."),
    ("AP_OFFICER", "Accounts Payable Officer", "Creates, uploads and submits invoices."),
    ("MANAGER", "Manager", "Reviews and decides on invoices assigned to them."),
    ("AUDITOR", "Auditor", "Investigates suspicious invoices, views audit logs, exports reports."),
]


def create_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name, description in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name, "description": description})


def remove_roles(apps, schema_editor):
    apps.get_model("accounts", "Role").objects.filter(code__in=[code for code, _, _ in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(create_roles, remove_roles)]
