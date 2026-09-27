"""Date-range query parameters shared by analytics and report exports (?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD)."""

from datetime import date

from django.utils import timezone
from rest_framework.exceptions import ValidationError

MAX_RANGE_DAYS = 5 * 366          # keeps queries and PDFs a sensible size
DEFAULT_MONTHS = 12


def _parse(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "Use the format YYYY-MM-DD."})


def start_of_months_back(day, months):
    """The 1st of the month `months - 1` months before `day`: 12 -> the last 12 whole calendar months."""
    index = day.year * 12 + day.month - 1 - (months - 1)
    return date(index // 12, index % 12 + 1, 1)


def date_range(params, default_months=DEFAULT_MONTHS):
    """(date_from, date_to), both inclusive. Missing values: the last `default_months` calendar months up to today."""
    today = timezone.localdate()
    date_to = _parse(params["date_to"], "date_to") if params.get("date_to") else today
    date_from = (_parse(params["date_from"], "date_from") if params.get("date_from")
                 else start_of_months_back(date_to, default_months))
    if date_from > date_to:
        raise ValidationError({"date_from": "The start date must be on or before the end date."})
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise ValidationError({"date_from": "Choose a range of at most 5 years."})
    return date_from, date_to


def months_between(date_from, date_to):
    """['2025-10', ..., '2026-09']: every month touched by the range, oldest first."""
    keys, year, month = [], date_from.year, date_from.month
    while (year, month) <= (date_to.year, date_to.month):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return keys
