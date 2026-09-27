"""Invoice business logic. Views, the importer and seed data all call these functions."""

from django.db import IntegrityError, transaction

from audit.models import AuditLog
from audit.services import log_action
from common.exceptions import BusinessError

from .models import Invoice, InvoiceItem

AUDITED_FIELDS = (
    "invoice_number", "vendor_id", "invoice_date", "due_date", "amount", "currency", "tax", "description",
    "purchase_category", "purchase_order_number", "department", "payment_bank_account_id",
)


def _snapshot(invoice):
    return {field: getattr(invoice, field) for field in AUDITED_FIELDS}


def _duplicate_error(vendor, invoice_number, existing_id):
    return BusinessError(
        "DUPLICATE_INVOICE_NUMBER",
        f"Invoice number '{invoice_number}' already exists for vendor '{vendor}'.",
        status_code=409, details={"invoice_number": invoice_number, "existing_invoice_id": existing_id},
    )


def _ensure_unique_number(vendor, invoice_number, exclude_pk=None):
    existing = Invoice.objects.filter(vendor=vendor, invoice_number=invoice_number).exclude(pk=exclude_pk).first()
    if existing:
        raise _duplicate_error(vendor, invoice_number, existing.pk)


def _replace_items(invoice, items):
    invoice.items.all().delete()
    for item in items:
        InvoiceItem.objects.create(invoice=invoice, **item)  # save() computes line_total


@transaction.atomic
def create_invoice(user, data, request=None):
    """Create a DRAFT invoice. `data` is InvoiceWriteSerializer.validated_data."""
    data = dict(data)
    items = data.pop("items", [])
    vendor = data["vendor"]
    if not data.get("department"):
        data["department"] = user.department
    if not data.get("payment_bank_account"):
        data["payment_bank_account"] = vendor.active_bank_account

    _ensure_unique_number(vendor, data["invoice_number"])
    try:
        with transaction.atomic():  # savepoint: a race on the unique constraint becomes a clean 409
            invoice = Invoice.objects.create(submitted_by=user, **data)
    except IntegrityError:
        raise _duplicate_error(vendor, data["invoice_number"], None)
    _replace_items(invoice, items)

    log_action(AuditLog.Action.INVOICE_CREATED, user=user, entity=invoice, request=request,
               description=f"Invoice {invoice.invoice_number} created for {vendor}", new_value=_snapshot(invoice))
    return invoice


@transaction.atomic
def update_invoice(user, invoice, data, request=None):
    """Edit a DRAFT invoice. Submitted invoices are frozen (their analysis refers to these values)."""
    if not invoice.is_editable:
        raise BusinessError(
            "INVOICE_NOT_EDITABLE",
            f"Only draft invoices can be edited. This invoice is {invoice.get_approval_status_display().lower()}.",
            status_code=409,
        )
    data = dict(data)
    items = data.pop("items", None)
    vendor = data.get("vendor", invoice.vendor)
    number = data.get("invoice_number", invoice.invoice_number)
    if vendor != invoice.vendor or number != invoice.invoice_number:
        _ensure_unique_number(vendor, number, exclude_pk=invoice.pk)
    if vendor != invoice.vendor and "payment_bank_account" not in data:
        data["payment_bank_account"] = vendor.active_bank_account

    before = _snapshot(invoice)
    for field, value in data.items():
        setattr(invoice, field, value)
    invoice.save()
    if items is not None:
        _replace_items(invoice, items)

    after = _snapshot(invoice)
    changed = [field for field in AUDITED_FIELDS if before[field] != after[field]]
    if changed or items is not None:
        log_action(AuditLog.Action.INVOICE_UPDATED, user=user, entity=invoice, request=request,
                   description=f"Invoice {invoice.invoice_number} edited",
                   old_value={f: before[f] for f in changed}, new_value={f: after[f] for f in changed})
    return invoice


@transaction.atomic
def delete_invoice(user, invoice, request=None):
    if not invoice.is_editable:
        raise BusinessError("INVOICE_NOT_DELETABLE", "Only draft invoices can be deleted.", status_code=409)
    snapshot, pk, number = _snapshot(invoice), invoice.pk, invoice.invoice_number
    invoice.delete()
    log_action(AuditLog.Action.INVOICE_DELETED, user=user, entity_type="invoice", entity_id=pk,
               request=request, description=f"Draft invoice {number} deleted", old_value=snapshot)
