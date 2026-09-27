"""Who reviews an invoice: department first, fewest pending, never the submitter, sensible fallbacks."""

from django.test import TestCase

from approvals.models import Approval
from common.test_utils import make_invoice, make_user
from fraud.models import FraudAlert

from .assignment import pick_auditor, pick_manager
from .models import User


class PickManagerTests(TestCase):
    def setUp(self):
        self.it_manager = make_user("MANAGER", department="IT")
        self.finance_manager = make_user("MANAGER", department="Finance")

    def test_prefers_the_invoice_department(self):
        self.assertEqual(pick_manager("it"), self.it_manager)          # case-insensitive
        self.assertEqual(pick_manager("Finance"), self.finance_manager)

    def test_falls_back_to_any_manager_with_the_fewest_pending(self):
        Approval.objects.create(invoice=make_invoice(), level="MANAGER", assigned_to=self.it_manager)
        self.assertEqual(pick_manager("Marketing"), self.finance_manager)
        self.assertEqual(pick_manager(""), self.finance_manager)

    def test_balances_load_within_a_department(self):
        second_it = make_user("MANAGER", department="IT")
        Approval.objects.create(invoice=make_invoice(), level="MANAGER", assigned_to=self.it_manager)
        self.assertEqual(pick_manager("IT"), second_it)

    def test_never_the_submitter(self):
        self.assertEqual(pick_manager("IT", exclude_user=self.it_manager), self.finance_manager)

    def test_inactive_managers_are_skipped(self):
        self.it_manager.is_active = False
        self.it_manager.save()
        self.assertEqual(pick_manager("IT"), self.finance_manager)

    def test_no_manager_left_falls_back_to_an_auditor(self):
        auditor = make_user("AUDITOR")
        User.objects.filter(role__code="MANAGER").update(is_active=False)
        with self.assertLogs("accounts.assignment", "WARNING"):
            self.assertEqual(pick_manager("IT"), auditor)


class PickAuditorTests(TestCase):
    def test_fewest_open_alerts_then_pending(self):
        busy, free = make_user("AUDITOR"), make_user("AUDITOR")
        FraudAlert.objects.create(invoice=make_invoice(), primary_type="DUPLICATE", severity="HIGH", assigned_to=busy)
        self.assertEqual(pick_auditor(), free)
        FraudAlert.objects.create(invoice=make_invoice(), primary_type="DUPLICATE", severity="HIGH", assigned_to=free,
                                  status="RESOLVED", outcome="CLEARED")          # closed alerts do not count
        self.assertEqual(pick_auditor(), free)

    def test_never_the_submitter_and_none_when_nobody_is_left(self):
        only = make_user("AUDITOR")
        with self.assertLogs("accounts.assignment", "WARNING"):
            self.assertIsNone(pick_auditor(exclude_user=only))
