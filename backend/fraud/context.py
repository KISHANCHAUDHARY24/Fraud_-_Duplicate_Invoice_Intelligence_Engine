"""
Build the JSON payload for POST /api/v1/fraud/analyze from the database.

This mirrors ml-service/training/context.py, which rebuilt the same context for
training, so the live model sees inputs computed the same way as its training data:
    * statistics only from invoices submitted BEFORE this one (no look-ahead)
    * drafts never count; rejected invoices do not count as normal spending
    * population standard deviation (as in training)
    * bank accounts only as masked values; full numbers are never stored or sent
"""

import math
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Q, StdDev

from common.text import normalize_vendor_name
from invoices.models import Invoice
from system_settings.services import get_all_settings

from .models import FraudAlert

Status = Invoice.ApprovalStatus
NOT_SUBMITTED = [Status.DRAFT]
NOT_SPENDING = [Status.DRAFT, Status.REJECTED]
RECENT_DAYS = 31
MAX_CANDIDATES = 200
AMOUNT_BAND = 0.10   # duplicate candidates from other vendors: amount within +/-10%


def _snapshot(invoice: Invoice) -> dict:
    return {
        "id": invoice.pk, "invoice_number": invoice.invoice_number, "vendor_id": invoice.vendor_id,
        "vendor_name": invoice.vendor.vendor_name, "amount": float(invoice.amount), "currency": invoice.currency,
        "invoice_date": invoice.invoice_date.isoformat(), "description": invoice.description,
    }


def _history(invoice: Invoice) -> dict:
    return {**_snapshot(invoice), "department": invoice.department}


def _population_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def vendor_context(invoice: Invoice) -> dict:
    earlier = (Invoice.objects.filter(vendor_id=invoice.vendor_id, submission_date__lt=invoice.submission_date)
               .exclude(pk=invoice.pk).exclude(approval_status__in=NOT_SPENDING))
    history = list(earlier.values_list("amount", "invoice_date"))
    amounts = [float(amount) for amount, _ in history]
    dates = [invoice_date for _, invoice_date in history]

    company = (Invoice.objects.filter(submission_date__lt=invoice.submission_date).exclude(pk=invoice.pk)
               .exclude(approval_status__in=NOT_SPENDING).aggregate(avg=Avg("amount"), std=StdDev("amount")))
    first_date = min(dates, default=invoice.invoice_date)
    months_active = max(1.0, (invoice.invoice_date - first_date).days / 30.4)
    vendor = invoice.vendor
    vendor_invoices = Invoice.objects.filter(vendor=vendor).exclude(pk=invoice.pk)
    # A vendor with a year of invoices is not "new", even if its record was created recently
    # (e.g. imported from an older system), so age counts from the earlier of the two.
    first_seen = min(filter(None, [vendor.created_at.date(), min(dates, default=None)]))

    return {
        "vendor_invoice_count": len(amounts),
        "vendor_avg_amount": sum(amounts) / len(amounts) if amounts else None,
        "vendor_std_amount": _population_std(amounts),
        "company_avg_amount": float(company["avg"]) if company["avg"] is not None else None,
        "company_std_amount": float(company["std"]) if company["std"] is not None else None,
        "invoices_last_30_days": sum(1 for d in dates if 0 <= (invoice.invoice_date - d).days <= 30),
        "avg_monthly_invoices": len(amounts) / months_active if amounts else 0.0,
        "days_since_previous_invoice": max(0, (invoice.invoice_date - max(dates)).days) if dates else None,
        "vendor_age_days": max(0, (invoice.submission_date.date() - first_seen).days),
        "vendor_status": vendor.status,
        "open_alert_count": FraudAlert.objects.filter(invoice__in=vendor_invoices,
                                                      status__in=FraudAlert.OPEN_STATUSES).count(),
        "confirmed_issue_count": vendor_invoices.filter(
            fraud_status=Invoice.FraudStatus.REVIEWED_CONFIRMED_ISSUE).count(),
    }


def bank_context(invoice: Invoice) -> dict:
    vendor = invoice.vendor
    current = invoice.payment_bank_account or vendor.active_bank_account
    if current is None:
        return {}
    # By id, not created_at: two accounts saved within one Windows clock tick share a timestamp
    # (see docs/database.md §4.5); ids always increase in creation order.
    previous = vendor.bank_accounts.filter(id__lt=current.id).order_by("-id").first()
    last_paid = (Invoice.objects.filter(vendor=vendor, approval_status__in=[Status.APPROVED, Status.PAID],
                                        payment_bank_account__isnull=False)
                 .exclude(pk=invoice.pk).select_related("payment_bank_account")
                 .order_by("-submission_date", "-id").first())
    last_paid_account = last_paid.payment_bank_account if last_paid else None
    return {
        "current_account_masked": current.masked_account,
        "current_account_age_days": max(0, (invoice.submission_date.date() - current.valid_from).days),
        "previous_account_masked": previous.masked_account if previous else None,
        "differs_from_last_paid": bool(last_paid_account and last_paid_account.pk != current.pk),
        "last_paid_account_masked": last_paid_account.masked_account if last_paid_account else None,
    }


def recent_vendor_invoices(invoice: Invoice) -> list[dict]:
    window = (invoice.invoice_date - timedelta(days=RECENT_DAYS), invoice.invoice_date + timedelta(days=RECENT_DAYS))
    rows = (Invoice.objects.filter(vendor_id=invoice.vendor_id, invoice_date__range=window)
            .exclude(pk=invoice.pk).exclude(approval_status__in=NOT_SPENDING).select_related("vendor"))
    return [_history(row) for row in rows]


def duplicate_candidates(invoice: Invoice, lookback_days: int) -> list[dict]:
    """
    Earlier submitted invoices worth comparing (docs/duplicate-detection.md §2): same vendor,
    a vendor with a similar name, or a similar amount, within the look-back window.
    Rejected invoices are included: a rejected invoice sent again is exactly what we look for.
    """
    since = invoice.invoice_date - timedelta(days=lookback_days)
    first_word = (normalize_vendor_name(invoice.vendor.vendor_name).split() or [""])[0]
    amount = invoice.amount
    band = amount * Decimal(str(AMOUNT_BAND))
    related = Q(vendor_id=invoice.vendor_id) | Q(amount__gte=amount - band, amount__lte=amount + band)
    if first_word:
        related |= Q(vendor__normalized_name__startswith=first_word)
    rows = (Invoice.objects.filter(related, invoice_date__gte=since).exclude(pk=invoice.pk)
            .exclude(approval_status__in=NOT_SUBMITTED).select_related("vendor")
            .order_by("-invoice_date", "-id")[:MAX_CANDIDATES])
    return [_snapshot(row) for row in rows]


def build_analysis_payload(invoice: Invoice) -> dict:
    config = get_all_settings()
    return {
        "invoice": {**_history(invoice), "submission_datetime": invoice.submission_date.isoformat()},
        "vendor_context": vendor_context(invoice),
        "bank": bank_context(invoice),
        "recent_vendor_invoices": recent_vendor_invoices(invoice),
        "duplicate_candidates": duplicate_candidates(invoice, int(config["duplicate_lookback_days"])),
        "config": config,
    }
