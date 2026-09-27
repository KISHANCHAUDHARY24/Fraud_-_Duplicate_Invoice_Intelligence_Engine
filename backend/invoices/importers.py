"""
Bulk invoice import from CSV or JSON (docs/api.md §2.5).

    Upload → validate file → validate columns → for each row:
        resolve vendor → validate types/required fields (InvoiceWriteSerializer)
        → reject duplicates inside the file → create invoice (own savepoint)
    → summary {total_rows, created, failed, errors[], invoice_ids[]}

Partial success: valid rows are saved, invalid rows are reported with their row
number, so the user fixes only those rows and re-uploads them.
"""

import csv
import io
import re
from dataclasses import asdict, dataclass, field

from django.conf import settings
from django.db import transaction

from audit.models import AuditLog
from audit.services import log_action
from common.exceptions import BusinessError
from common.text import normalize_vendor_name
from vendors.models import Vendor

from . import services
from .serializers import InvoiceWriteSerializer

REQUIRED_COLUMNS = ("invoice_number", "vendor", "amount", "invoice_date", "description")
OPTIONAL_COLUMNS = ("due_date", "currency", "tax", "purchase_category", "purchase_order_number", "department")
KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

TEMPLATE_ROWS = [
    ["INV-1001", "ACME Corp", "5000.00", "2026-09-01", "Software licence renewal", "2026-10-01", "USD", "0",
     "SOFTWARE", "PO-7788", "IT"],
    ["INV-1002", "Global Ltd", "9900.00", "2026-09-02", "Hardware purchase", "", "USD", "0",
     "HARDWARE", "", "Operations"],
]

_MONEY_NOISE = re.compile(r"[\s,$€£₹]")


@dataclass
class ImportResult:
    total_rows: int = 0
    created: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    invoice_ids: list = field(default_factory=list)

    def add_error(self, row, field_name, message):
        self.errors.append({"row": row, "field": field_name, "message": message})


def _invalid(message, details=None):
    return BusinessError("INVALID_IMPORT_FILE", message, status_code=400, details=details)


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------
def read_csv(uploaded_file):
    """Validate the uploaded file and return a list of row dicts (header names lower-cased)."""
    if uploaded_file is None:
        raise _invalid("No file uploaded. Send the CSV in a form field named 'file'.")
    if not uploaded_file.name.lower().endswith(".csv"):
        raise _invalid("Only .csv files are accepted.")
    if uploaded_file.size > settings.IMPORT_MAX_FILE_BYTES:
        raise _invalid(f"File is too large. Maximum size is {settings.IMPORT_MAX_FILE_BYTES // 1024} KB.")

    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "cp1252"):  # Excel on Windows often saves CSV as cp1252
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise _invalid("Could not read the file. Save it as 'CSV UTF-8' and try again.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise _invalid("The file is empty.")
    headers = [(name or "").strip().lower() for name in reader.fieldnames]
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise _invalid(f"Missing required column(s): {', '.join(missing)}.",
                       {"missing_columns": missing, "required_columns": list(REQUIRED_COLUMNS)})
    reader.fieldnames = headers

    rows = list(reader)
    if not rows:
        raise _invalid("The file has a header but no invoice rows.")
    _check_row_limit(len(rows))
    return rows


def read_json(payload):
    """Accept either a JSON list of invoices or {"invoices": [...]}."""
    rows = payload.get("invoices") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise _invalid('Send a non-empty JSON list of invoices, or {"invoices": [...]}.')
    _check_row_limit(len(rows))
    return rows


def _check_row_limit(count):
    if count > settings.IMPORT_MAX_ROWS:
        raise _invalid(f"Too many rows ({count}). The maximum per upload is {settings.IMPORT_MAX_ROWS}.")


# ---------------------------------------------------------------------------
# Row processing
# ---------------------------------------------------------------------------
class VendorResolver:
    """Find a vendor by id (JSON), exact name, registration number, or equivalent name."""

    def __init__(self):
        vendors = list(Vendor.objects.all())
        self.by_id = {v.pk: v for v in vendors}
        self.by_name = {v.vendor_name.strip().lower(): v for v in vendors}
        self.by_registration = {v.registration_number.strip().lower(): v for v in vendors if v.registration_number}
        self.by_normalized = {}
        for v in vendors:
            self.by_normalized.setdefault(v.normalized_name, []).append(v)

    def resolve(self, value):
        if isinstance(value, int) and not isinstance(value, bool):
            return self.by_id.get(value)
        text = str(value or "").strip().lower()
        if not text:
            return None
        found = self.by_name.get(text) or self.by_registration.get(text)
        if found:
            return found
        candidates = self.by_normalized.get(normalize_vendor_name(text), [])
        return candidates[0] if len(candidates) == 1 else None  # ambiguous -> ask user to be exact


def _clean_row(row):
    """Trim strings, drop empty optional cells (so defaults apply), tidy amounts and categories."""
    cleaned = {}
    for key, value in row.items():
        key = (key or "").strip().lower()
        if key not in KNOWN_COLUMNS and key != "items":
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        cleaned[key] = value
    for money_field in ("amount", "tax"):
        if isinstance(cleaned.get(money_field), str):
            cleaned[money_field] = _MONEY_NOISE.sub("", cleaned[money_field])
    if isinstance(cleaned.get("purchase_category"), str):
        cleaned["purchase_category"] = cleaned["purchase_category"].upper().replace(" ", "_")
    return cleaned


def _flatten_errors(detail, prefix=""):
    """{'amount': ['A valid number is required.']} -> [('amount', 'A valid number is required.')]"""
    if isinstance(detail, dict):
        for key, value in detail.items():
            yield from _flatten_errors(value, f"{prefix}{key}" if not prefix else f"{prefix}.{key}")
    elif isinstance(detail, list):
        for item in detail:
            yield from _flatten_errors(item, prefix)
    else:
        yield (prefix or "row", str(detail))


def import_rows(rows, user, request=None, first_row_number=2, source="CSV"):
    """
    first_row_number is 2 for CSV (line 1 is the header) and 1 for JSON,
    so reported row numbers match what the user sees in their file.
    """
    result = ImportResult()
    vendors = VendorResolver()
    seen_in_file = {}

    for offset, raw in enumerate(rows):
        row_number = first_row_number + offset
        if not isinstance(raw, dict):
            result.total_rows += 1
            result.failed += 1
            result.add_error(row_number, "row", "Each invoice must be a JSON object.")
            continue
        row = _clean_row(raw)
        if not row:
            continue  # completely blank line
        result.total_rows += 1

        missing = [column for column in REQUIRED_COLUMNS if column not in row]
        if missing:
            result.failed += 1
            for column in missing:
                result.add_error(row_number, column, "This field is required.")
            continue

        vendor = vendors.resolve(row["vendor"])
        if vendor is None:
            result.failed += 1
            result.add_error(row_number, "vendor",
                             f"Unknown vendor '{row['vendor']}'. Create the vendor first or use its exact name.")
            continue
        row["vendor"] = vendor.pk

        serializer = InvoiceWriteSerializer(data=row)
        if not serializer.is_valid():
            result.failed += 1
            for field_name, message in _flatten_errors(serializer.errors):
                result.add_error(row_number, field_name, message)
            continue

        key = (vendor.pk, serializer.validated_data["invoice_number"])
        if key in seen_in_file:
            result.failed += 1
            result.add_error(row_number, "invoice_number",
                             f"Duplicate of row {seen_in_file[key]} in this file (same vendor and invoice number).")
            continue
        seen_in_file[key] = row_number

        try:
            with transaction.atomic():  # savepoint: a failing row never affects the others
                invoice = services.create_invoice(user, serializer.validated_data, request=request)
        except BusinessError as exc:
            result.failed += 1
            result.add_error(row_number, "invoice_number", str(exc.detail))
            continue
        result.created += 1
        result.invoice_ids.append(invoice.pk)

    log_action(
        AuditLog.Action.INVOICE_UPLOADED, user=user, entity_type="invoice", request=request,
        description=f"{source} import: {result.created} created, {result.failed} failed of {result.total_rows} rows",
        new_value={"created": result.created, "failed": result.failed, "invoice_ids": result.invoice_ids},
    )
    return asdict(result)


def csv_template():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(KNOWN_COLUMNS)
    writer.writerows(TEMPLATE_ROWS)
    return buffer.getvalue()
