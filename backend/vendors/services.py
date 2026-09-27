"""Vendor business logic, called by vendors/views.py and by seed data."""

import hashlib
import hmac
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from audit.services import log_action
from common.exceptions import BusinessError
from common.text import normalize_vendor_name
from notifications.models import Notification
from notifications.services import notify_roles

from .models import Vendor, VendorBankAccount

_ACCOUNT_SEPARATORS = re.compile(r"[\s\-]")
_ACCOUNT_FORMAT = re.compile(r"^[A-Z0-9]{6,34}$")  # plain account numbers and IBANs

AUDITED_VENDOR_FIELDS = ("vendor_name", "registration_number", "address", "email", "phone", "status")


# ---------------------------------------------------------------------------
# Bank accounts
# ---------------------------------------------------------------------------
def normalize_account_number(raw):
    number = _ACCOUNT_SEPARATORS.sub("", str(raw or "")).upper()
    if not _ACCOUNT_FORMAT.match(number):
        raise ValidationError({"account_number": "Account number must be 6-34 letters or digits."})
    return number


def hash_account_number(number):
    """Keyed hash: the same account always gives the same hash; the hash cannot be reversed."""
    key = settings.BANK_HASH_KEY.encode()
    return hmac.new(key, normalize_account_number(number).encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def add_bank_account(vendor, bank_name, account_number, user=None, request=None):
    """
    Register a new active bank account for a vendor. The previous active account
    is closed, not deleted, so the change history is kept. A *change* is a
    classic payment-redirection fraud vector, so Admins and Auditors are notified.
    """
    bank_name = (bank_name or "").strip()
    if not bank_name:
        raise ValidationError({"bank_name": "Bank name is required."})
    number = normalize_account_number(account_number)
    account_hash = hash_account_number(number)
    today = timezone.localdate()

    previous = vendor.bank_accounts.select_for_update().filter(is_active=True).first()
    if previous and previous.account_hash == account_hash:
        raise ValidationError({"account_number": "This bank account is already the vendor's active account."})
    if previous:
        previous.is_active = False
        previous.valid_to = today
        previous.save(update_fields=["is_active", "valid_to"])

    account = VendorBankAccount.objects.create(
        vendor=vendor, bank_name=bank_name, account_last4=number[-4:],
        account_hash=account_hash, valid_from=today, added_by=user,
    )

    log_action(
        AuditLog.Action.VENDOR_BANK_ACCOUNT_CHANGED if previous else AuditLog.Action.VENDOR_BANK_ACCOUNT_ADDED,
        user=user, entity=vendor, request=request,
        description=f"Bank account for {vendor} set to {account}",
        # Masked values only: never write full account numbers to the audit log.
        old_value={"bank_account": str(previous)} if previous else None,
        new_value={"bank_account": str(account)},
    )
    if previous:
        notify_roles(
            ["ADMIN", "AUDITOR"], Notification.Type.VENDOR_RISK_ALERT,
            title=f"Bank account changed for {vendor}",
            message=f"{previous} was replaced by {account}. Invoices to this vendor will be flagged for review.",
            exclude=user,
        )
    return account


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------
def _snapshot(vendor):
    return {field: getattr(vendor, field) for field in AUDITED_VENDOR_FIELDS}


def _ensure_not_duplicate(vendor_name, exclude_pk=None):
    """'ACME Corp' and 'ACME Corporation' are the same vendor: duplicate vendor records are a fraud risk."""
    normalized = normalize_vendor_name(vendor_name)
    clash = Vendor.objects.filter(normalized_name=normalized).exclude(pk=exclude_pk).first()
    if clash:
        raise BusinessError(
            "VENDOR_ALREADY_EXISTS",
            f"A vendor with an equivalent name already exists: '{clash.vendor_name}' (id {clash.pk}).",
            status_code=409, details={"existing_vendor_id": clash.pk},
        )


@transaction.atomic
def create_vendor(user, request=None, bank_name=None, account_number=None, **fields):
    _ensure_not_duplicate(fields["vendor_name"])
    vendor = Vendor.objects.create(**fields)
    log_action(AuditLog.Action.VENDOR_CREATED, user=user, entity=vendor, request=request,
               description=f"Vendor {vendor} created", new_value=_snapshot(vendor))
    if account_number:
        add_bank_account(vendor, bank_name, account_number, user=user, request=request)
    return vendor


@transaction.atomic
def update_vendor(user, vendor, request=None, **fields):
    if "vendor_name" in fields:
        _ensure_not_duplicate(fields["vendor_name"], exclude_pk=vendor.pk)
    before = _snapshot(vendor)
    for name, value in fields.items():
        setattr(vendor, name, value)
    vendor.save()
    after = _snapshot(vendor)
    changed = {key for key in before if before[key] != after[key]}
    if changed:
        log_action(AuditLog.Action.VENDOR_UPDATED, user=user, entity=vendor, request=request,
                   description=f"Vendor {vendor} modified",
                   old_value={k: before[k] for k in changed}, new_value={k: after[k] for k in changed})
    return vendor


@transaction.atomic
def delete_vendor(user, vendor, request=None):
    if vendor.invoices.exists():
        raise BusinessError(
            "VENDOR_HAS_INVOICES",
            "This vendor has invoices and cannot be deleted. Set its status to Inactive instead.",
            status_code=409,
        )
    snapshot, pk = _snapshot(vendor), vendor.pk
    vendor.delete()
    log_action(AuditLog.Action.VENDOR_DELETED, user=user, entity_type="vendor", entity_id=pk,
               request=request, description=f"Vendor {snapshot['vendor_name']} deleted", old_value=snapshot)
