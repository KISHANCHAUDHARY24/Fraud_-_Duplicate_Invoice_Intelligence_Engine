"""Authentication and user-management logic (called by accounts/views.py)."""

import logging

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.db import transaction
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditLog
from audit.services import log_action
from common.exceptions import BusinessError

from .models import User

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_MESSAGE = "Invalid username or password."


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def revoke_all_tokens(user):
    """Blacklist every refresh token ever issued to the user (logout everywhere)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# ---------------------------------------------------------------------------
# Login / logout / password
# ---------------------------------------------------------------------------
def login(request, username, password):
    """
    Returns the user on success. On failure raises INVALID_CREDENTIALS with the
    same message whether the username or the password was wrong, so attackers
    cannot discover which usernames exist. Inactive users cannot log in.
    """
    user = authenticate(request, username=username, password=password)
    if user is None:
        safe_username = (username or "")[:150]
        logger.warning("Failed login for username %r", safe_username)  # never log the password
        log_action(
            AuditLog.Action.USER_LOGIN_FAILED, entity_type="user",
            description=f"Failed login attempt for username '{safe_username}'", request=request,
        )
        raise BusinessError("INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE, status_code=status.HTTP_401_UNAUTHORIZED)

    update_last_login(None, user)
    log_action(AuditLog.Action.USER_LOGIN, user=user, entity=user, description=f"{user.username} logged in", request=request)
    return user


def logout(request, user, refresh_token):
    token = RefreshToken(refresh_token)  # raises TokenError if invalid or expired
    if str(token.get("user_id")) != str(user.pk):
        raise BusinessError("TOKEN_INVALID", "This token does not belong to the current user.", status_code=400)
    token.blacklist()
    log_action(AuditLog.Action.USER_LOGOUT, user=user, entity=user, description=f"{user.username} logged out", request=request)


@transaction.atomic
def change_password(request, user, new_password):
    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoke_all_tokens(user)  # other devices must log in again
    log_action(AuditLog.Action.PASSWORD_CHANGED, user=user, entity=user, description="Password changed", request=request)
    return issue_tokens(user)  # keep the current session alive


# ---------------------------------------------------------------------------
# User management (Admin)
# ---------------------------------------------------------------------------
AUDITED_USER_FIELDS = ("email", "first_name", "last_name", "department", "is_active")


def _snapshot(user):
    data = {field: getattr(user, field) for field in AUDITED_USER_FIELDS}
    data["role"] = user.role_code
    return data


@transaction.atomic
def create_user(request, actor, password, **fields):
    user = User(**fields)
    user.set_password(password)
    user.save()
    log_action(
        AuditLog.Action.USER_CREATED, user=actor, entity=user,
        description=f"User {user.username} created", new_value=_snapshot(user), request=request,
    )
    return user


@transaction.atomic
def update_user(request, actor, user, **fields):
    before = _snapshot(user)
    for name, value in fields.items():
        setattr(user, name, value)
    user.save()
    after = _snapshot(user)
    if before == after:
        return user

    changed_old = {k: v for k, v in before.items() if after[k] != v}
    changed_new = {k: after[k] for k in changed_old}
    action = AuditLog.Action.ROLE_CHANGED if "role" in changed_new else AuditLog.Action.USER_UPDATED
    log_action(
        action, user=actor, entity=user, description=f"User {user.username} updated",
        old_value=changed_old, new_value=changed_new, request=request,
    )
    return user


@transaction.atomic
def set_user_active(request, actor, user, active):
    if not active and user.pk == actor.pk:
        raise BusinessError("CANNOT_DEACTIVATE_SELF", "You cannot deactivate your own account.", status_code=409)
    if user.is_active == active:
        return user
    user.is_active = active
    user.save(update_fields=["is_active"])
    if not active:
        revoke_all_tokens(user)
    log_action(
        AuditLog.Action.USER_UPDATED if active else AuditLog.Action.USER_DEACTIVATED,
        user=actor, entity=user,
        description=f"User {user.username} {'reactivated' if active else 'deactivated'}",
        old_value={"is_active": not active}, new_value={"is_active": active}, request=request,
    )
    return user
