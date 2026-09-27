"""
Per-key validation for Admin-editable settings. A bad value here would silently
break fraud detection, so every key has an explicit rule. Each validator returns
the cleaned value or raises serializers.ValidationError with a readable message.
"""

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework.serializers import ValidationError

from fraud.models import SignalType

DUPLICATE_COMPONENTS = {"invoice_number", "vendor", "amount", "date", "description"}
SIGNAL_TYPES = {value for value, _ in SignalType.choices}
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _number(value, low=None, high=None, integer=False, low_inclusive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("Must be a number.")
    if integer and int(value) != value:
        raise ValidationError("Must be a whole number.")
    if low is not None and (value < low if low_inclusive else value <= low):
        raise ValidationError(f"Must be {'at least' if low_inclusive else 'greater than'} {low}.")
    if high is not None and value > high:
        raise ValidationError(f"Must be at most {high}.")
    return int(value) if integer else value


def number(low=None, high=None, integer=False, low_inclusive=True):
    return lambda value: _number(value, low, high, integer, low_inclusive)


def boolean(value):
    if not isinstance(value, bool):
        raise ValidationError("Must be true or false.")
    return value


def timezone_name(value):
    if not isinstance(value, str):
        raise ValidationError("Must be a timezone name such as 'Asia/Kolkata' or 'Europe/London'.")
    try:
        ZoneInfo(value.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"Unknown timezone '{value}'.")
    return value.strip()


def duplicate_weights(value):
    if not isinstance(value, dict) or set(value) != DUPLICATE_COMPONENTS:
        raise ValidationError(f"Must contain exactly these keys: {', '.join(sorted(DUPLICATE_COMPONENTS))}.")
    cleaned = {key: _number(weight, 0, 1) for key, weight in value.items()}
    if abs(sum(cleaned.values()) - 1) > 0.001:
        raise ValidationError(f"Weights must add up to 1.0 (currently {sum(cleaned.values()):.3f}).")
    return cleaned


def working_hours(value):
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        raise ValidationError('Must look like {"start": "08:00", "end": "19:00"}.')
    if not all(isinstance(value[k], str) and _TIME.match(value[k]) for k in ("start", "end")):
        raise ValidationError("Times must use 24-hour HH:MM format.")
    if value["start"] >= value["end"]:
        raise ValidationError("Start time must be before end time.")
    return value


def working_days(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("Must be a non-empty list of day numbers (Monday=0 ... Sunday=6).")
    days = [_number(day, 0, 6, integer=True) for day in value]
    if len(set(days)) != len(days):
        raise ValidationError("Days must not repeat.")
    return sorted(days)


def risk_level_thresholds(value):
    if not isinstance(value, dict) or set(value) != {"medium", "high", "critical"}:
        raise ValidationError('Must look like {"medium": 30, "high": 60, "critical": 80}.')
    cleaned = {key: _number(v, 1, 100, integer=True) for key, v in value.items()}
    if not cleaned["medium"] < cleaned["high"] < cleaned["critical"]:
        raise ValidationError("Thresholds must increase: medium < high < critical.")
    return cleaned


def signal_weights(value):
    if not isinstance(value, dict) or set(value) != SIGNAL_TYPES:
        raise ValidationError(f"Must contain exactly these signal types: {', '.join(sorted(SIGNAL_TYPES))}.")
    return {key: _number(v, 0, 100, integer=True) for key, v in value.items()}


def signal_floors(value):
    if not isinstance(value, dict) or not set(value) <= SIGNAL_TYPES:
        raise ValidationError(f"Keys must be signal types: {', '.join(sorted(SIGNAL_TYPES))}.")
    cleaned = {}
    for key, floor in value.items():
        if not isinstance(floor, dict) or set(floor) != {"min_strength", "min_score"}:
            raise ValidationError(f'{key}: must look like {{"min_strength": 0.9, "min_score": 60}}.')
        cleaned[key] = {"min_strength": _number(floor["min_strength"], 0, 1),
                        "min_score": _number(floor["min_score"], 0, 100, integer=True)}
    return cleaned


VALIDATORS = {
    "approval_threshold": number(0, low_inclusive=False),
    "near_threshold_percent": number(0, 50, low_inclusive=False),
    "auto_approve_low_risk": boolean,
    "duplicate_threshold": number(1, 100, integer=True),
    "duplicate_weights": duplicate_weights,
    "duplicate_lookback_days": number(1, 3650, integer=True),
    "working_hours": working_hours,
    "working_days": working_days,
    "timezone": timezone_name,
    "split_window_days": number(1, 90, integer=True),
    "split_min_invoices": number(1, 20, integer=True),
    "round_amount_base": number(1, integer=True),
    "bank_change_window_days": number(1, 365, integer=True),
    "ml_anomaly_threshold": number(0, 1),
    "risk_level_thresholds": risk_level_thresholds,
    "signal_weights": signal_weights,
    "signal_floors": signal_floors,
}


def validate_setting(key, value):
    return VALIDATORS[key](value)
