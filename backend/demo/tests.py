"""seed_data: accounts, history consistency, scenario timing, idempotency, safety. The ML service is mocked."""

from datetime import datetime
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from approvals.models import Approval
from common.test_utils import fake_analysis, make_invoice, make_user, make_vendor
from fraud.models import FraudAnalysis
from invoices.models import Invoice
from vendors.models import Vendor

from . import seed
from .data import DEFAULT_PASSWORD, DEMO_REG_PREFIX, HISTORY_MONTHS, HISTORY_PER_MONTH, VENDORS

ANALYZE = "fraud.services.ml_client.analyze"
HEALTH = "demo.management.commands.seed_data.ml_client.health"
MODEL_UP = {"status": "ok", "model_loaded": True, "model_version": "iforest-test"}
FIXED_NOW = datetime(2026, 9, 24, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))   # a Thursday
HISTORY_TOTAL = len(VENDORS) * HISTORY_MONTHS * HISTORY_PER_MONTH


def fake_ml(payload):
    """What the model would say for each scenario invoice (enough for routing and the report)."""
    number = payload["invoice"]["invoice_number"]
    return {
        "INV1001": fake_analysis("HIGH", 64, [("DUPLICATE", 30, "98% similarity with invoice INV-1001")]),
        "AC-2003": fake_analysis("MEDIUM", 40, [("TIME_ANOMALY", 10, "Sunday 02:17"), ("AMOUNT_ANOMALY", 15, "9x average")]),
        "BP-3003": fake_analysis("MEDIUM", 56, [("SPLIT_PURCHASE", 20, "3 invoices under the threshold")]),
        "FL-2005": fake_analysis("HIGH", 60, [("BANK_ACCOUNT_CHANGE", 20, "Bank account changed 1 day ago")]),
    }.get(number, fake_analysis("LOW", 0))


def run(*args, ml_up=True):
    out = StringIO()
    with mock.patch(HEALTH, return_value=MODEL_UP if ml_up else None), \
            mock.patch(ANALYZE, side_effect=fake_ml) as analyze, \
            mock.patch("demo.seed.timezone.now", return_value=FIXED_NOW):
        call_command("seed_data", "--allow-without-debug", "--noinput", *args, stdout=out)
    return out.getvalue(), analyze


class SeedDataTests(TestCase):
    def test_creates_accounts_history_and_scenarios(self):
        output, analyze = run()
        for username in ("admin", "ap_officer", "manager", "auditor"):
            self.assertTrue(User.objects.get(username=username).check_password(DEFAULT_PASSWORD))
        self.assertEqual(Vendor.objects.filter(registration_number__startswith=DEMO_REG_PREFIX).count(), len(VENDORS))
        self.assertEqual(Invoice.objects.filter(analyses__model_version="seed-baseline").count(), HISTORY_TOTAL)
        self.assertEqual(analyze.call_count, 8)   # normal, 2 duplicate, unusual, 3 split, bank change
        self.assertEqual(output.count("OK   "), 5)
        self.assertEqual(Invoice.objects.get(invoice_number="EV-2001").approval_status, Invoice.ApprovalStatus.PAID)
        self.assertEqual(Invoice.objects.filter(approval_status=Invoice.ApprovalStatus.DRAFT).count(), 2)
        auditor_review = Approval.objects.get(invoice__invoice_number="INV1001", decision="PENDING")
        self.assertEqual(auditor_review.level, "AUDITOR")

    def test_scenario_submission_times_are_fixed_business_moments(self):
        run()
        zone = ZoneInfo("Asia/Kolkata")
        unusual = Invoice.objects.get(invoice_number="AC-2003").submission_date.astimezone(zone)
        self.assertEqual((unusual.strftime("%A"), unusual.hour, unusual.minute), ("Sunday", 2, 17))
        normal = Invoice.objects.get(invoice_number="EV-2001").submission_date.astimezone(zone)
        self.assertEqual((normal.date().isoformat(), normal.hour, normal.minute), ("2026-09-23", 11, 20))  # the weekday before
        for number in ("INV-1001", "BP-3001", "BP-3002", "BP-3003"):
            self.assertLess(Invoice.objects.get(invoice_number=number).submission_date.astimezone(zone).weekday(), 5)

    def test_history_is_consistent(self):
        run("--no-scenarios")
        approvals = Approval.objects.filter(invoice__analyses__model_version="seed-baseline")
        self.assertEqual(approvals.count(), HISTORY_TOTAL)
        for approval in approvals:
            self.assertGreaterEqual(approval.decided_at, approval.created_at)       # never a negative "time to decide"
            self.assertGreaterEqual(approval.created_at, approval.invoice.submission_date)
        zone = ZoneInfo("Asia/Kolkata")
        for invoice in Invoice.objects.all():
            local = invoice.submission_date.astimezone(zone)
            self.assertTrue(local.weekday() < 5 and 9 <= local.hour <= 16, invoice.invoice_number)   # office hours
            self.assertLess(invoice.submission_date, FIXED_NOW)
        self.assertIn(seed.BASELINE_NOTE, FraudAnalysis.objects.first().raw_response["warnings"])

    def test_running_twice_adds_nothing(self):
        run()
        counts = (Invoice.objects.count(), Vendor.objects.count(), User.objects.count(), Approval.objects.count())
        _, analyze = run()
        self.assertEqual((Invoice.objects.count(), Vendor.objects.count(), User.objects.count(), Approval.objects.count()), counts)
        self.assertEqual(analyze.call_count, 0)

    def test_ml_down_leaves_drafts_that_a_later_run_analyses(self):
        output, analyze = run(ml_up=False)
        self.assertIn("created as DRAFTS", output)
        self.assertEqual(analyze.call_count, 0)
        self.assertEqual(Invoice.objects.get(invoice_number="INV1001").approval_status, Invoice.ApprovalStatus.DRAFT)
        _, analyze = run()
        self.assertEqual(analyze.call_count, 8)
        self.assertEqual(Invoice.objects.get(invoice_number="INV1001").risk_level, "HIGH")

    def test_reset_removes_only_demo_data(self):
        own_vendor = make_vendor(vendor_name="Real Supplier")
        make_invoice(vendor=own_vendor, invoice_number="REAL-1")
        run()
        run("--reset", "--no-scenarios")
        self.assertTrue(Invoice.objects.filter(invoice_number="REAL-1").exists())
        self.assertFalse(Invoice.objects.filter(invoice_number="INV1001").exists())            # scenarios gone
        self.assertEqual(Invoice.objects.filter(analyses__model_version="seed-baseline").count(), HISTORY_TOTAL)  # history rebuilt
        self.assertTrue(User.objects.filter(username="manager").exists())                         # accounts kept

    def test_never_touches_a_real_account_with_a_demo_username(self):
        real = make_user("ADMIN", username="admin", email="it-head@company.example", password="Their0wn!Pass")
        with self.assertRaisesMessage(CommandError, "non-demo accounts: admin"):
            run()
        real.refresh_from_db()
        self.assertTrue(real.check_password("Their0wn!Pass"))

    @override_settings(DEBUG=False)
    def test_refuses_without_debug(self):
        with self.assertRaisesMessage(CommandError, "Run it only in development"):
            call_command("seed_data", stdout=StringIO())

    def test_custom_password(self):
        run("--password", "Another#Demo42", "--no-scenarios")
        self.assertTrue(User.objects.get(username="auditor").check_password("Another#Demo42"))


class DateHelperTests(TestCase):
    def test_business_day_helpers(self):
        from datetime import date
        monday, sunday = date(2026, 9, 21), date(2026, 9, 20)
        self.assertEqual(seed.last_weekday_before(monday), date(2026, 9, 18))      # Friday
        self.assertEqual(seed.last_sunday_before(monday), sunday)
        self.assertEqual(seed.last_sunday_before(sunday), date(2026, 9, 13))       # strictly before
        self.assertEqual(seed.weekdays_before(date(2026, 9, 23), 3), date(2026, 9, 18))
