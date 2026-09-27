from copy import deepcopy

from django.db import transaction

from audit.models import AuditLog
from audit.services import log_action

from .defaults import DEFAULT_SETTINGS
from .models import SystemSetting


def get_setting(key):
    """Current value of a setting, falling back to the built-in default."""
    if key not in DEFAULT_SETTINGS:
        raise KeyError(f"Unknown setting: {key}")
    row = SystemSetting.objects.filter(key=key).only("value").first()
    return row.value if row else deepcopy(DEFAULT_SETTINGS[key][0])


def get_all_settings():
    """All settings as a plain dict (sent to the ML service with each analysis)."""
    values = {key: deepcopy(default) for key, (default, _, _) in DEFAULT_SETTINGS.items()}
    values.update(dict(SystemSetting.objects.filter(key__in=values).values_list("key", "value")))
    return values


def ensure_setting_row(key):
    default, value_type, description = DEFAULT_SETTINGS[key]
    row, _ = SystemSetting.objects.get_or_create(
        key=key, defaults={"value": deepcopy(default), "value_type": value_type, "description": description},
    )
    return row


@transaction.atomic
def update_setting(user, key, value, request=None):
    """Store an already-validated value and record old/new values in the audit log."""
    row = ensure_setting_row(key)
    old_value = row.value
    if old_value == value:
        return row
    row.value = value
    row.updated_by = user
    row.save(update_fields=["value", "updated_by", "updated_at"])
    log_action(AuditLog.Action.SETTINGS_CHANGED, user=user, entity_type="system_setting", entity_id=key,
               request=request, description=f"Setting '{key}' changed",
               old_value={"value": old_value}, new_value={"value": value})
    return row
