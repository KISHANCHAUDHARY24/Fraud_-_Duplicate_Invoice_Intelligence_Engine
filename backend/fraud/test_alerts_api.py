"""Fraud alert list, investigation payload, assign, mark reviewed, resolve; re-analyse and similar."""

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from approvals.models import Approval, Payment
from common.test_utils import fake_analysis, make_invoice, make_user, make_vendor
from invoices.models import Invoice

from . import ml_client
from .models import FraudAlert

Status = Invoice.ApprovalStatus
ANALYZE = "fraud.services.ml_client.analyze"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class AlertTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER", department="IT")
        self.other_ap = make_user("AP_OFFICER")
        self.auditor = make_user("AUDITOR")
        self.second_auditor = make_user("AUDITOR")
        self.manager = make_user("MANAGER", department="IT")
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.original = make_invoice(vendor=self.vendor, submitted_by=self.ap, invoice_number="INV-1001",
                                     amount=Decimal("5000"), approval_status=Status.APPROVED)
        self.invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap, invoice_number="INV1001",
                                    amount=Decimal("5000"), department="IT")
        duplicate = {"duplicate_score": 98, "is_possible_duplicate": True, "matched_invoice_id": self.original.pk,
                     "matched_invoice_number": "INV-1001", "components": None, "reasons": ["Same vendor"],
                     "candidates": [{"invoice_id": self.original.pk, "invoice_number": "INV-1001", "vendor_name": "ACME Corp",
                                     "score": 98, "components": {"invoice_number": 1.0, "vendor": 1.0, "amount": 1.0,
                                                                 "date": 0.93, "description": 0.9}}]}
        result = fake_analysis("CRITICAL", 85, [("DUPLICATE", 30, "98% similarity with invoice INV-1001", self.original.pk),
                                                ("BANK_ACCOUNT_CHANGE", 20, "Bank change")], duplicate=duplicate)
        with mock.patch(ANALYZE, return_value=result):
            client_for(self.ap).post(f"/api/invoices/{self.invoice.pk}/submit/")
        self.alert = FraudAlert.objects.get(invoice=self.invoice)
        self.url = f"/api/fraud/alerts/{self.alert.pk}"

    def test_alert_list_filters_and_visibility(self):
        auditor = client_for(self.auditor)
        self.assertEqual(auditor.get("/api/fraud/alerts/?severity=CRITICAL&type=BANK_ACCOUNT_CHANGE").json()["count"], 1)
        self.assertEqual(auditor.get("/api/fraud/alerts/?type=TIME_ANOMALY").json()["count"], 0)
        row = auditor.get("/api/fraud/alerts/").json()["results"][0]
        self.assertEqual(set(row["signal_types"]), {"DUPLICATE", "BANK_ACCOUNT_CHANGE"})
        self.assertEqual(client_for(self.ap).get("/api/fraud/alerts/").json()["count"], 1)        # own invoice
        self.assertEqual(client_for(self.other_ap).get("/api/fraud/alerts/").json()["count"], 0)  # not theirs
        self.assertEqual(client_for(self.other_ap).get(f"{self.url}/").status_code, 404)

    def test_investigation_payload(self):
        body = client_for(self.auditor).get(f"{self.url}/").json()
        self.assertEqual(set(body), {"alert", "invoice", "vendor", "similar_invoices", "vendor_history",
                                     "approval_history", "audit_history"})
        self.assertEqual(body["invoice"]["latest_analysis"]["risk_score"], 85)
        self.assertEqual(body["similar_invoices"][0]["invoice"]["invoice_number"], "INV-1001")
        self.assertEqual(body["similar_invoices"][0]["score"], 98)
        duplicate_signal = next(s for s in body["invoice"]["latest_analysis"]["signals"] if s["signal_type"] == "DUPLICATE")
        self.assertEqual(duplicate_signal["related_invoice_number"], "INV-1001")
        self.assertIn("INVOICE_BLOCKED", [e["action"] for e in body["audit_history"]])
        self.assertEqual(body["vendor"]["vendor_name"], "ACME Corp")

    def test_auditor_list_for_assigning(self):
        inactive = make_user("AUDITOR")
        inactive.is_active = False
        inactive.save()
        rows = client_for(self.auditor).get("/api/fraud/alerts/auditors/").json()
        self.assertEqual({row["id"] for row in rows}, {self.auditor.pk, self.second_auditor.pk})
        self.assertEqual(set(rows[0]), {"id", "name"})                  # nothing beyond the name
        self.assertEqual(client_for(self.manager).get("/api/fraud/alerts/auditors/").status_code, 403)

    def test_closed_alert_cannot_be_reopened_or_reassigned(self):
        auditor = client_for(self.auditor)
        self.assertEqual(auditor.post(f"{self.url}/mark-reviewed/").status_code, 200)
        self.assertEqual(auditor.post(f"{self.url}/mark-reviewed/").status_code, 409)   # already in review
        auditor.post(f"{self.url}/resolve/", {"outcome": "CLEARED", "note": "Checked with vendor"}, format="json")
        response = auditor.post(f"{self.url}/mark-reviewed/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE_TRANSITION")
        self.assertEqual(auditor.post(f"{self.url}/assign/", {"auditor": self.second_auditor.pk}, format="json").status_code, 409)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, FraudAlert.Status.RESOLVED)

    def test_assign_and_mark_reviewed(self):
        response = client_for(self.auditor).post(f"{self.url}/assign/", {"auditor": self.second_auditor.pk}, format="json")
        self.assertEqual(response.json()["assigned_to"], self.second_auditor.pk)
        bad = client_for(self.auditor).post(f"{self.url}/assign/", {"auditor": self.manager.pk}, format="json")
        self.assertEqual(bad.status_code, 400)
        reviewed = client_for(self.second_auditor).post(f"{self.url}/mark-reviewed/").json()
        self.assertEqual(reviewed["status"], "IN_REVIEW")
        self.assertEqual(client_for(self.manager).post(f"{self.url}/mark-reviewed/").status_code, 403)

    def test_resolve_cleared_unblocks_for_auditor_approval(self):
        self.assertEqual(client_for(self.auditor).post(f"{self.url}/resolve/", {"outcome": "CLEARED"},
                                                       format="json").status_code, 400)   # note required
        response = client_for(self.auditor).post(f"{self.url}/resolve/", {
            "outcome": "CLEARED", "note": "Vendor confirmed the new account by phone"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.approval_status, self.invoice.fraud_status), (Status.UNDER_REVIEW, "REVIEWED_CLEARED"))
        approval = Approval.objects.get(invoice=self.invoice, decision="PENDING")
        self.assertEqual((approval.level, approval.assigned_to), ("AUDITOR", self.auditor))
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())    # the block is lifted
        again = client_for(self.auditor).post(f"{self.url}/resolve/", {"outcome": "CLEARED", "note": "x"}, format="json")
        self.assertEqual(again.status_code, 409)

    def test_resolve_confirmed_issue_rejects_invoice(self):
        response = client_for(self.auditor).post(f"{self.url}/resolve/", {
            "outcome": "CONFIRMED_ISSUE", "note": "Same invoice already paid as INV-1001"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.approval_status, self.invoice.fraud_status),
                         (Status.REJECTED, "REVIEWED_CONFIRMED_ISSUE"))
        self.assertEqual(Payment.objects.get(invoice=self.invoice).status, Payment.Status.BLOCKED)

    def test_only_humans_set_outcomes(self):
        self.assertEqual(self.alert.outcome, "")   # the system never decides the outcome


class ReanalyseAndSimilarTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER")
        self.manager = make_user("MANAGER")
        self.invoice = make_invoice(submitted_by=self.ap, amount=Decimal("100"))

    def test_reanalyse_after_ml_failure(self):
        with mock.patch(ANALYZE, side_effect=ml_client.MLServiceError("down")):
            client_for(self.ap).post(f"/api/invoices/{self.invoice.pk}/submit/")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.fraud_status, "ANALYSIS_FAILED")

        with mock.patch(ANALYZE, return_value=fake_analysis("MEDIUM", 35, [("TIME_ANOMALY", 35, "Late")])):
            response = client_for(self.ap).post(f"/api/invoices/{self.invoice.pk}/analyze/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["risk_score"], response.json()["fraud_status"]), (35, "FLAGGED"))
        self.assertEqual(response.json()["approval_status"], "UNDER_REVIEW")   # workflow status unchanged

    def test_reanalyse_when_ml_still_down_is_503(self):
        self.invoice.approval_status = Status.UNDER_REVIEW
        self.invoice.save()
        with mock.patch(ANALYZE, side_effect=ml_client.MLServiceError("Cannot reach the ML service")):
            response = client_for(self.ap).post(f"/api/invoices/{self.invoice.pk}/analyze/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "ML_SERVICE_UNAVAILABLE")

    def test_draft_cannot_be_reanalysed(self):
        self.assertEqual(client_for(self.ap).post(f"/api/invoices/{self.invoice.pk}/analyze/").status_code, 409)

    def test_similar_is_empty_before_analysis(self):
        self.assertEqual(client_for(self.ap).get(f"/api/invoices/{self.invoice.pk}/similar/").json(), [])
