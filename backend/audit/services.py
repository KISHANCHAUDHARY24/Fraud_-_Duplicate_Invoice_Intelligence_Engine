import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def client_ip(request):
    """Best-effort client IP. Local development has no proxy, so REMOTE_ADDR is trusted."""
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def log_action(action, user=None, entity=None, entity_type="", entity_id="",
               description="", old_value=None, new_value=None, request=None):
    """
    Record one audit entry. Pass either `entity` (any model instance) or an
    explicit entity_type/entity_id.

        log_action(AuditLog.Action.INVOICE_APPROVED, user=request.user, entity=invoice,
                   old_value={"status": "UNDER_REVIEW"}, new_value={"status": "APPROVED"},
                   request=request)

    Never pass passwords, tokens or full bank account numbers in the values.
    """
    if entity is not None:
        entity_type = entity_type or entity._meta.model_name
        entity_id = entity_id or str(entity.pk)
    if user is not None and not user.is_authenticated:
        user = None

    entry = AuditLog.objects.create(
        user=user, action=action, entity_type=entity_type, entity_id=str(entity_id),
        description=description, old_value=old_value, new_value=new_value,
        ip_address=client_ip(request),
    )
    logger.info("AUDIT %s %s#%s by %s", action, entity_type, entity_id, user or "system")
    return entry
