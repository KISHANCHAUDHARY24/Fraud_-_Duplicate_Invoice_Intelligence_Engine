"""
END-TO-END test over real HTTP: Django API -> real FastAPI service -> real trained model -> routing.

Skipped unless ML_LIVE_TESTS=1 and the ML service is running with a trained model:
    (ml-service)  python -m uvicorn main:app --port 8001
    (backend)     $env:ML_LIVE_TESTS = "1"; python manage.py test fraud.test_live_e2e

The five demo scenarios of docs/testing.md §5. Submission times are fixed (Asia/Kolkata)
so the result does not depend on when the test is run.
"""

import os
import unittest
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from approvals.models import Approval
from common.test_utils import make_invoice, make_user, make_vendor
from invoices.models import Invoice
from vendors.services import add_bank_account

from . import ml_client

IST = dt_timezone(timedelta(hours=5, minutes=30))
TUESDAY_1120 = datetime(2026, 9, 22, 11, 20, tzinfo=IST)
SUNDAY_0217 = datetime(2026, 9, 20, 2, 17, tzinfo=IST)
Status = Invoice.ApprovalStatus
LIVE = os.environ.get("ML_LIVE_TESTS") == "1"


@unittest.skipUnless(LIVE, "set ML_LIVE_TESTS=1 and start the ML service to run end-to-end tests")
class LiveEndToEndTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        health = ml_client.health()
        if not health or not health.get("model_loaded"):
            raise unittest.SkipTest("ML service not reachable or model not loaded")
        cls.model_version = health["model_version"]

    def setUp(self):
        self.ap = make_user("AP_OFFICER", department="IT")
        self.manager = make_user("MANAGER", department="IT")
        self.auditor = make_user("AUDITOR")
        self.client = APIClient()
        self.client.force_authenticate(self.ap)
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.account = add_bank_account(self.vendor, "HDFC Bank", "111122223333")
        self.account.valid_from = date(2025, 1, 1)
        self.account.save()
        # 12 months of normal history: ~1,500 per invoice, weekday office hours, already approved.
        for month in range(12):
            day = date(2025, 9, 10) + timedelta(days=30 * month)
            make_invoice(vendor=self.vendor, submitted_by=self.ap, invoice_number=f"AC-{1000 + month}",
                         amount=Decimal(1400 + 20 * (month % 5)), invoice_date=day, department="IT",
                         description="Office supplies", payment_bank_account=self.account,
                         approval_status=Status.APPROVED,
                         submission_date=datetime.combine(day, datetime.min.time(), tzinfo=IST) + timedelta(hours=11))

    def submit(self, invoice, at=TUESDAY_1120):
        with mock.patch("approvals.services.timezone.now", return_value=at):
            response = self.client.post(f"/api/invoices/{invoice.pk}/submit/")
        self.assertEqual(response.status_code, 200, response.json())
        invoice.refresh_from_db()
        body = response.json()
        print(f"\n  {invoice.invoice_number}: {body['latest_analysis']['summary']}")
        for line in body["latest_analysis"]["explanation"]:
            print(f"     + {line}")
        return body

    def review_level(self, invoice):
        approval = Approval.objects.filter(invoice=invoice, decision="PENDING").first()
        return approval.level if approval else None

    def new_invoice(self, **fields):
        data = dict(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("1480"), department="IT",
                    invoice_date=date(2026, 9, 21), description="Office supplies", payment_bank_account=self.account)
        data.update(fields)
        return make_invoice(**data)

    def test_1_normal_invoice_is_auto_approved(self):
        invoice = self.new_invoice(invoice_number="AC-2001")
        body = self.submit(invoice)
        self.assertEqual(body["latest_analysis"]["model_version"], self.model_version)
        self.assertEqual((invoice.risk_level, invoice.approval_status), ("LOW", Status.APPROVED))

    def test_2_duplicate_goes_to_auditor(self):
        make_invoice(vendor=self.vendor, submitted_by=self.ap, invoice_number="INV-1001", amount=Decimal("5000"),
                     invoice_date=date(2026, 9, 18), description="Software License", approval_status=Status.APPROVED,
                     payment_bank_account=self.account, submission_date=TUESDAY_1120 - timedelta(days=3))
        invoice = self.new_invoice(invoice_number="INV1001", amount=Decimal("5000"), description="Software licence",
                                   invoice_date=date(2026, 9, 20))
        body = self.submit(invoice)
        self.assertIn(invoice.risk_level, ("HIGH", "CRITICAL"))
        types = [s["signal_type"] for s in body["latest_analysis"]["signals"]]
        self.assertIn("DUPLICATE", types)
        self.assertIn(invoice.approval_status, (Status.UNDER_REVIEW, Status.BLOCKED))

    def test_3_unusual_invoice_goes_to_review(self):
        invoice = self.new_invoice(invoice_number="AC-2003", amount=Decimal("13500"), invoice_date=date(2026, 9, 19))
        body = self.submit(invoice, at=SUNDAY_0217)
        types = {s["signal_type"] for s in body["latest_analysis"]["signals"]}
        self.assertTrue({"TIME_ANOMALY", "AMOUNT_ANOMALY", "ML_ANOMALY"} <= types)
        self.assertIn(invoice.risk_level, ("MEDIUM", "HIGH", "CRITICAL"))
        self.assertEqual(invoice.approval_status, Status.UNDER_REVIEW)

    def test_4_split_purchase_goes_to_manager_or_higher(self):
        for number, amount, day in (("AC-3001", "9900", 15), ("AC-3002", "9700", 17)):
            make_invoice(vendor=self.vendor, submitted_by=self.ap, invoice_number=number, amount=Decimal(amount),
                         invoice_date=date(2026, 9, day), description="Office computer equipment", department="IT",
                         approval_status=Status.UNDER_REVIEW, payment_bank_account=self.account,
                         submission_date=TUESDAY_1120 - timedelta(days=22 - day))
        invoice = self.new_invoice(invoice_number="AC-3003", amount=Decimal("9800"), invoice_date=date(2026, 9, 18),
                                   description="Office computer equipment")
        body = self.submit(invoice)
        self.assertIn("SPLIT_PURCHASE", [s["signal_type"] for s in body["latest_analysis"]["signals"]])
        self.assertIn(invoice.risk_level, ("MEDIUM", "HIGH", "CRITICAL"))
        self.assertIn(self.review_level(invoice), ("MANAGER", "AUDITOR", None))

    def test_5_bank_account_change_goes_to_auditor(self):
        new_account = add_bank_account(self.vendor, "ICICI Bank", "444455556666")
        new_account.valid_from = date(2026, 9, 18)
        new_account.save()
        invoice = self.new_invoice(invoice_number="AC-2005", payment_bank_account=new_account)
        body = self.submit(invoice)
        self.assertIn("BANK_ACCOUNT_CHANGE", [s["signal_type"] for s in body["latest_analysis"]["signals"]])
        self.assertIn(invoice.risk_level, ("HIGH", "CRITICAL"))
        self.assertIn(invoice.approval_status, (Status.UNDER_REVIEW, Status.BLOCKED))
