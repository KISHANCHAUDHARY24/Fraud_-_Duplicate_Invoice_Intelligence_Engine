from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class SystemSetting(models.Model):
    """A single Admin-editable business setting stored as JSON (see defaults.py)."""

    class ValueType(models.TextChoices):
        INT = "INT", "Integer"
        DECIMAL = "DECIMAL", "Decimal"
        BOOL = "BOOL", "Boolean"
        STRING = "STRING", "Text"
        JSON = "JSON", "JSON"

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(encoder=DjangoJSONEncoder)
    value_type = models.CharField(max_length=10, choices=ValueType.choices)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"
