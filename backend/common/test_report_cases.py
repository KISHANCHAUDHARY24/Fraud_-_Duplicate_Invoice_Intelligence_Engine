"""
The sample test cases of the project report (docs/project-report/12-testing.md §12.4), one test each.
TC-04 (near-duplicate) and TC-05 (split purchase) are ML-service tests: see that chapter for their names.
"""

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from approvals.models import Approval
from common.test_utils import fake_analysis, make_invoice, make_user, make_vendor
from fraud import ml_client
from invoices.models import Invoice

ANALYZE = "fraud.services.ml_client.analyze"
Status = Invoice.ApprovalStatus


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class ReportTestCases(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER", username="ap_officer", password="Demo@12345", department="IT")
        self.manager = make_user("MANAGER", department="IT")
        self.auditor = make_user("AUDITOR")
        self.vendor = make_vendor(vendor_name="ACME Corp")

    def submit(self, invoice, outcome):
        patch = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
        with mock.patch(ANALYZE, **patch):
            response = client_for(self.ap).post(f"/api/invoices/{invoice.pk}/submit/")
        invoice.refresh_from_db()
        return response

    def test_tc01_login_with_valid_credentials(self):
        response = APIClient().post("/api/auth/login/", {"username": "ap_officer", "password": "Demo@12345"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue({"access", "refresh", "user"} <= set(response.json()))

    def test_tc02_ap_officer_cannot_approve(self):
        invoice = make_invoice(vendor=self.vendor, submitted_by=self.manager, approval_status=Status.UNDER_REVIEW)
        approval = Approval.objects.create(invoice=invoice, level="MANAGER", assigned_to=self.ap)   # even if assigned
        response = client_for(self.ap).post(f"/api/approvals/{approval.pk}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        invoice.refresh_from_db()
        self.assertEqual(invoice.approval_status, Status.UNDER_REVIEW)

    def test_tc03_negative_amount_is_rejected(self):
        response = client_for(self.ap).post("/api/invoices/", {
            "vendor": self.vendor.pk, "invoice_number": "INV-9", "invoice_date": "2026-09-01", "amount": "-5",
            "description": "Office supplies"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("amount", response.json()["error"]["details"])

    def test_tc06_critical_risk_is_blocked(self):
        invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("9950"))
        self.submit(invoice, fake_analysis("CRITICAL", 85, [("DUPLICATE", 30, "98% similar"), ("BANK_ACCOUNT_CHANGE", 20, "new account")]))
        self.assertEqual(invoice.approval_status, Status.BLOCKED)

    def test_tc07_ml_service_down_goes_to_manager_review(self):
        invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap)
        response = self.submit(invoice, ml_client.MLServiceError("Cannot reach the ML service"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(invoice.fraud_status, Invoice.FraudStatus.ANALYSIS_FAILED)
        self.assertEqual(Approval.objects.get(invoice=invoice, decision="PENDING").level, "MANAGER")

    def test_tc08_reject_without_comment_is_refused(self):
        invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap, approval_status=Status.UNDER_REVIEW)
        approval = Approval.objects.create(invoice=invoice, level="MANAGER", assigned_to=self.manager)
        response = client_for(self.manager).post(f"/api/approvals/{approval.pk}/reject/", {"comment": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, "PENDING")
