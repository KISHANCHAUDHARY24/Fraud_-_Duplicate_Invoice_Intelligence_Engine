"""
Phase 16: add escalation floors for a strong ML anomaly and an extreme amount (see docs/risk-scoring.md §10).

Existing databases are updated ONLY if signal_floors still has the old built-in value: a value an Admin
changed on purpose is left alone. Reversing restores the old value under the same condition.
"""

from django.db import migrations

OLD = {
    "DUPLICATE": {"min_strength": 0.9, "min_score": 60},
    "BANK_ACCOUNT_CHANGE": {"min_strength": 0.0, "min_score": 60},
    "SPLIT_PURCHASE": {"min_strength": 0.0, "min_score": 30},
}
NEW = {
    **OLD,
    "ML_ANOMALY": {"min_strength": 0.8, "min_score": 30},
    "AMOUNT_ANOMALY": {"min_strength": 1.0, "min_score": 30},
}


def _replace(apps, current, replacement):
    SystemSetting = apps.get_model("system_settings", "SystemSetting")
    SystemSetting.objects.filter(key="signal_floors", value=current).update(value=replacement)


def forwards(apps, schema_editor):
    _replace(apps, OLD, NEW)


def backwards(apps, schema_editor):
    _replace(apps, NEW, OLD)


class Migration(migrations.Migration):
    dependencies = [("system_settings", "0002_seed_defaults")]
    operations = [migrations.RunPython(forwards, backwards)]
