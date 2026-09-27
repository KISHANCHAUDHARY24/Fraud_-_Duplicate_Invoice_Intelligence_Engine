"""
Object-level access: WHICH invoices a user may see (docs/authentication.md §4).

Every view that returns invoices must start from visible_invoices(user).
Invoices outside the user's scope then simply "do not exist" for them (404).
"""

from django.db.models import Q

from .models import Invoice

Status = Invoice.ApprovalStatus


def _scope_filter(user):
    role = user.role_code
    if role in ("ADMIN", "AUDITOR"):
        # Auditors provide oversight: they must be able to compare a flagged invoice with normal
        # ones and read a vendor's full history. Their capabilities keep this read-only.
        return Q()
    if role == "AP_OFFICER":
        return Q(submitted_by=user)
    if role == "MANAGER":
        scope = Q(approvals__assigned_to=user)
        if user.department:
            scope |= Q(department__iexact=user.department) & ~Q(approval_status=Status.DRAFT)
        return scope
    return None  # no role: nothing visible


def visible_invoices(user, queryset=None):
    queryset = Invoice.objects.all() if queryset is None else queryset
    scope = _scope_filter(user)
    if scope is None:
        return queryset.none()
    if not scope:  # Admin / Auditor: unrestricted
        return queryset
    # Sub-query instead of .distinct(): the joins (approvals, alerts) cannot duplicate rows.
    return queryset.filter(pk__in=Invoice.objects.filter(scope).values("pk"))
