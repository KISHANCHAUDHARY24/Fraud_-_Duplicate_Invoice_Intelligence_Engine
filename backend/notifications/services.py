"""Create in-app notifications. Called by other apps' services."""

from accounts.models import User

from .models import Notification


def notify(recipients, type, title, message="", invoice=None, exclude=None):
    """Create one notification per active recipient (duplicates and `exclude` removed)."""
    seen, created = set(), []
    for user in recipients:
        if user is None or not user.is_active or user.pk in seen or (exclude and user.pk == exclude.pk):
            continue
        seen.add(user.pk)
        created.append(Notification(recipient=user, type=type, title=title[:200], message=message, invoice=invoice))
    return Notification.objects.bulk_create(created)


def notify_roles(role_codes, type, title, message="", invoice=None, exclude=None):
    """Notify every active user holding one of the roles (superusers count as ADMIN)."""
    users = User.objects.filter(is_active=True, role__code__in=role_codes)
    if "ADMIN" in role_codes:
        users = users | User.objects.filter(is_active=True, is_superuser=True, role__isnull=True)
    return notify(users.distinct(), type, title, message, invoice, exclude)
