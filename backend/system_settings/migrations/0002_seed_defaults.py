"""Data migration: copy the default business rules into the SystemSetting table."""

from django.db import migrations


def create_defaults(apps, schema_editor):
    # Imported here so later edits to defaults.py only affect NEW settings
    # (existing rows are never overwritten).
    from system_settings.defaults import DEFAULT_SETTINGS

    SystemSetting = apps.get_model("system_settings", "SystemSetting")
    for key, (value, value_type, description) in DEFAULT_SETTINGS.items():
        SystemSetting.objects.get_or_create(
            key=key, defaults={"value": value, "value_type": value_type, "description": description},
        )


class Migration(migrations.Migration):
    dependencies = [("system_settings", "0001_initial")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
