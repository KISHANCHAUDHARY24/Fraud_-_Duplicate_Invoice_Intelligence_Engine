import re

from django.db import IntegrityError, transaction
from django.test import TestCase

from common.test_utils import make_invoice, make_user

from .models import Approval, Payment


class ApprovalModelTests(TestCase):
    def test_only_one_pending_approval_per_invoice(self):
        invoice = make_invoice()
        manager = make_user("MANAGER")
        Approval.objects.create(invoice=invoice, level=Approval.Level.MANAGER, assigned_to=manager)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Approval.objects.create(invoice=invoice, level=Approval.Level.AUDITOR, assigned_to=manager)

    def test_decided_approvals_do_not_block_a_new_pending_one(self):
        invoice = make_invoice()
        manager, auditor = make_user("MANAGER"), make_user("AUDITOR")
        Approval.objects.create(invoice=invoice, level=Approval.Level.MANAGER, assigned_to=manager,
                                decision=Approval.Decision.ESCALATED)
        Approval.objects.create(invoice=invoice, level=Approval.Level.AUDITOR, assigned_to=auditor)


class PaymentModelTests(TestCase):
    def test_simulated_payment_gets_a_unique_reference(self):
        first = Payment.objects.create(invoice=make_invoice(), amount=100)
        second = Payment.objects.create(invoice=make_invoice(), amount=200)
        self.assertRegex(first.reference, re.compile(r"^SIM-PAY-[0-9A-F]{10}$"))
        self.assertNotEqual(first.reference, second.reference)

    def test_payment_amount_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            Payment.objects.create(invoice=make_invoice(), amount=0)
