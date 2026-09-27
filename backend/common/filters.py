from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """
    Like DRF's OrderingFilter, but empty values always sort last.
    PostgreSQL puts NULL first in DESC order, so "?ordering=-risk_score" would otherwise
    list not-yet-analysed invoices above the riskiest ones.
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        expressions = []
        for field in ordering:
            if isinstance(field, str):
                descending = field.startswith("-")
                expression = F(field.lstrip("-"))
                field = expression.desc(nulls_last=True) if descending else expression.asc(nulls_last=True)
            expressions.append(field)
        return queryset.order_by(*expressions, "pk")  # pk: stable order for pagination
