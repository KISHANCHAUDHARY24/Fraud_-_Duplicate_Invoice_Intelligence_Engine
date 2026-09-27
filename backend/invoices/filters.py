from django_filters import rest_framework as filters

from .models import Invoice


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    """?approval_status=UNDER_REVIEW,BLOCKED"""


class InvoiceFilter(filters.FilterSet):
    approval_status = CharInFilter(field_name="approval_status")
    fraud_status = CharInFilter(field_name="fraud_status")
    risk_level = CharInFilter(field_name="risk_level")
    purchase_category = CharInFilter(field_name="purchase_category")
    vendor = filters.NumberFilter(field_name="vendor_id")
    submitted_by = filters.NumberFilter(field_name="submitted_by_id")
    department = filters.CharFilter(field_name="department", lookup_expr="iexact")
    date_from = filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="invoice_date", lookup_expr="lte")
    submitted_from = filters.DateFilter(field_name="submission_date__date", lookup_expr="gte")
    submitted_to = filters.DateFilter(field_name="submission_date__date", lookup_expr="lte")
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    risk_score_min = filters.NumberFilter(field_name="risk_score", lookup_expr="gte")

    class Meta:
        model = Invoice
        fields = []
