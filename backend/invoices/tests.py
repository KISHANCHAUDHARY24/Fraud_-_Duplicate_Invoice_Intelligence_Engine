from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from common.test_utils import make_invoice, make_user, make_vendor
from vendors.services import add_bank_account

from .models import Invoice, InvoiceItem

Status = Invoice.ApprovalStatus


class InvoiceConstraintTests(TestCase):
    """Rules enforced by PostgreSQL itself, so no code path can bypass them."""

    def setUp(self):
        self.vendor = make_vendor()
        self.user = make_user()

    def assert_rejected_by_database(self, **fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_invoice(vendor=self.vendor, submitted_by=self.user, **fields)

    def test_defaults_for_a_new_invoice(self):
        invoice = make_invoice(vendor=self.vendor, submitted_by=self.user)
        self.assertEqual(invoice.approval_status, Status.DRAFT)
        self.assertEqual(invoice.fraud_status, Invoice.FraudStatus.NOT_ANALYZED)
        self.assertIsNone(invoice.risk_score)

    def test_exact_duplicate_number_for_same_vendor_is_rejected(self):
        make_invoice(vendor=self.vendor, submitted_by=self.user, invoice_number="INV-1001")
        self.assert_rejected_by_database(invoice_number="INV-1001")

    def test_near_duplicate_number_is_allowed_to_be_saved(self):
        # Near duplicates are saved and later *flagged* by the ML service.
        make_invoice(vendor=self.vendor, submitted_by=self.user, invoice_number="INV-1001")
        make_invoice(vendor=self.vendor, submitted_by=self.user, invoice_number="INV1001")

    def test_same_number_for_different_vendors_is_allowed(self):
        make_invoice(vendor=self.vendor, submitted_by=self.user, invoice_number="INV-1")
        make_invoice(vendor=make_vendor(), submitted_by=self.user, invoice_number="INV-1")

    def test_amount_must_be_positive(self):
        self.assert_rejected_by_database(amount=Decimal("0"))
        self.assert_rejected_by_database(amount=Decimal("-5"))

    def test_tax_cannot_be_negative(self):
        self.assert_rejected_by_database(tax=Decimal("-1"))

    def test_due_date_cannot_be_before_invoice_date(self):
        self.assert_rejected_by_database(invoice_date=date(2026, 9, 10), due_date=date(2026, 9, 1))

    def test_risk_score_cannot_exceed_100(self):
        self.assert_rejected_by_database(risk_score=101)


class InvoiceValidationTests(TestCase):
    """Friendly validation (model.clean) used by serializers and forms."""

    def test_clean_reports_readable_errors(self):
        invoice = Invoice(
            invoice_number="X", vendor=make_vendor(), submitted_by=make_user(), description="x",
            amount=Decimal("-1"), invoice_date=date.today() + timedelta(days=3),
        )
        with self.assertRaises(ValidationError) as ctx:
            invoice.full_clean()
        errors = ctx.exception.message_dict
        self.assertIn("Invoice amount must be greater than zero.", errors["amount"])
        self.assertIn("Invoice date cannot be in the future.", errors["invoice_date"])

    def test_payment_account_must_belong_to_invoice_vendor(self):
        other_account = add_bank_account(make_vendor(), "HDFC Bank", "999988887777")
        invoice = make_invoice(payment_bank_account=None)
        invoice.payment_bank_account = other_account
        with self.assertRaises(ValidationError) as ctx:
            invoice.full_clean()
        self.assertIn("payment_bank_account", ctx.exception.message_dict)


class InvoiceStateMachineTests(TestCase):
    def test_happy_path(self):
        invoice = make_invoice()
        for status in [Status.SUBMITTED, Status.PROCESSING, Status.UNDER_REVIEW, Status.APPROVED, Status.PAID]:
            invoice.transition_to(status)
        self.assertEqual(invoice.approval_status, Status.PAID)

    def test_illegal_transitions_are_rejected(self):
        invoice = make_invoice()
        with self.assertRaises(ValidationError):
            invoice.transition_to(Status.APPROVED)  # DRAFT cannot jump to APPROVED
        invoice.approval_status = Status.REJECTED
        self.assertFalse(invoice.can_transition_to(Status.APPROVED))  # final state

    def test_only_drafts_are_editable(self):
        invoice = make_invoice()
        self.assertTrue(invoice.is_editable)
        invoice.transition_to(Status.SUBMITTED)
        self.assertFalse(invoice.is_editable)


class InvoiceItemTests(TestCase):
    def test_line_total_is_calculated(self):
        item = InvoiceItem.objects.create(
            invoice=make_invoice(), description="Laptop", quantity=Decimal("3"), unit_price=Decimal("499.99"),
        )
        self.assertEqual(item.line_total, Decimal("1499.97"))
