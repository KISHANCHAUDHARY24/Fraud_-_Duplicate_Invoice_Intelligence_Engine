"""Small builders shared by the rule / feature tests."""

from datetime import date, datetime, timedelta, timezone

from schemas.fraud import AnalysedInvoice, HistoryInvoice

IST = timezone(timedelta(hours=5, minutes=30))
TUESDAY_11AM_IST = datetime(2026, 9, 15, 11, 0, tzinfo=IST)   # a normal working moment
SUNDAY_0217_IST = datetime(2026, 9, 20, 2, 17, tzinfo=IST)


def invoice(**overrides) -> AnalysedInvoice:
    data = dict(id=100, invoice_number="INV-2001", vendor_id=4, vendor_name="ACME Corp", amount=1200.0,
                invoice_date=date(2026, 9, 15), description="Office supplies", department="IT",
                submission_datetime=TUESDAY_11AM_IST)
    data.update(overrides)
    return AnalysedInvoice(**data)


def history(invoice_id, amount, invoice_date, description="Office computer equipment", department="IT", **extra):
    return HistoryInvoice(id=invoice_id, invoice_number=f"INV-{invoice_id}", vendor_id=4, vendor_name="ACME Corp",
                          amount=amount, invoice_date=invoice_date, description=description,
                          department=department, **extra)
