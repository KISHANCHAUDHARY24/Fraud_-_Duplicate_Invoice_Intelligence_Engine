"""
Choosing who reviews an invoice (docs/approval-workflow.md §3).

Simple, explainable load balancing:
  * Manager: same department as the invoice if possible, then the fewest pending approvals.
  * Auditor: the fewest open alerts + pending approvals.
  * Never the person who submitted the invoice (separation of duties).
"""

import logging

from django.db.models import Count, Q

from .models import Role, User

logger = logging.getLogger(__name__)


def _candidates(role_code: str, exclude_user=None):
    users = User.objects.filter(is_active=True, role__code=role_code)
    if exclude_user is not None:
        users = users.exclude(pk=exclude_user.pk)
    return users.annotate(
        pending=Count("assigned_approvals", filter=Q(assigned_approvals__decision="PENDING"), distinct=True),
        open_alerts=Count("assigned_alerts", filter=Q(assigned_alerts__status__in=["OPEN", "IN_REVIEW"]), distinct=True),
    )


def pick_manager(department: str = "", exclude_user=None):
    managers = _candidates(Role.Code.MANAGER, exclude_user)
    if department:
        same_department = managers.filter(department__iexact=department).order_by("pending", "id").first()
        if same_department:
            return same_department
    manager = managers.order_by("pending", "id").first()
    if manager is None:
        logger.warning("No active manager available; falling back to an auditor")
        return pick_auditor(exclude_user)
    return manager


def pick_auditor(exclude_user=None):
    auditor = _candidates(Role.Code.AUDITOR, exclude_user).order_by("open_alerts", "pending", "id").first()
    if auditor is None:
        logger.warning("No active auditor available: review item left unassigned")
    return auditor
