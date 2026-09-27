"""Submit -> analyse -> route, and every reviewer decision (docs/approval-workflow.md)."""

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import fake_analysis, make_invoice, make_user, make_vendor
from fraud import ml_client
from fraud.models import FraudAlert, FraudAnalysis, FraudSignal
from invoices.models import Invoice
from notifications.models import Notification
from system_settings.models import SystemSetting

from .models import Approval, Payment

Status = Invoice.ApprovalStatus
ANALYZE = "fraud.services.ml_client.analyze"

LOW = fake_analysis("LOW", 5, [("ROUND_AMOUNT", 5, "Round amount")])
MEDIUM = fake_analysis("MEDIUM", 40, [("SPLIT_PURCHASE", 20, "Potential Split Purchase"), ("THRESHOLD_PROXIMITY", 20, "Near threshold")])
HIGH = fake_analysis("HIGH", 60, [("BANK_ACCOUNT_CHANGE", 20, "Vendor bank account changed 4 day(s) ago")])
CRITICAL = fake_analysis("CRITICAL", 85, [("DUPLICATE", 30, "98% similarity with invoice INV-1001"),
                                          ("BANK_ACCOUNT_CHANGE", 20, "Bank change"), ("TIME_ANOMALY", 10, "Sunday 02:17")])


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class WorkflowTestCase(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER", department="IT")
        self.manager = make_user("MANAGER", department="IT")
        self.other_manager = make_user("MANAGER", department="HR")
        self.auditor = make_user("AUDITOR")
        self.admin = make_user("ADMIN")
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("2500"), department="IT")

    def submit(self, result=LOW, invoice=None, user=None):
        invoice = invoice or self.invoice
        patch = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
        with mock.patch(ANALYZE, **patch):
            response = client_for(user or self.ap).post(f"/api/invoices/{invoice.pk}/submit/")
        invoice.refresh_from_db()
        return response

    def pending(self, invoice=None):
        return Approval.objects.get(invoice=invoice or self.invoice, decision=Approval.Decision.PENDING)


class RoutingTests(WorkflowTestCase):
    def test_low_risk_within_threshold_is_auto_approved(self):
        response = self.submit(LOW)
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self.invoice.approval_status, Status.APPROVED)
        self.assertEqual((self.invoice.risk_score, self.invoice.risk_level), (5, "LOW"))
        auto = Approval.objects.get(invoice=self.invoice)
        self.assertEqual((auto.decision, auto.decided_by, auto.assigned_to), ("APPROVED", None, None))
        self.assertEqual(Payment.objects.get(invoice=self.invoice).status, Payment.Status.SCHEDULED)
        self.assertEqual(response.json()["latest_analysis"]["explanation"], ["Round amount (+5)"])

    def test_analysis_and_signals_are_stored(self):
        self.submit(MEDIUM)
        analysis = FraudAnalysis.objects.get(invoice=self.invoice)
        self.assertEqual((analysis.risk_score, analysis.model_version), (40, "iforest-test"))
        self.assertEqual(sorted(FraudSignal.objects.filter(analysis=analysis).values_list("signal_type", "points")),
                         [("SPLIT_PURCHASE", 20), ("THRESHOLD_PROXIMITY", 20)])
        actions = list(AuditLog.objects.filter(entity_type="invoice", entity_id=str(self.invoice.pk))
                       .order_by("timestamp", "id").values_list("action", flat=True))
        self.assertEqual(actions[-3:], ["INVOICE_SUBMITTED", "FRAUD_ANALYSIS_EXECUTED", "INVOICE_ROUTED"])

    def test_low_risk_above_threshold_goes_to_manager(self):
        self.invoice.amount = Decimal("15000")
        self.invoice.save()
        self.submit(LOW)
        self.assertEqual(self.invoice.approval_status, Status.UNDER_REVIEW)
        self.assertEqual(self.pending().level, Approval.Level.MANAGER)

    def test_auto_approval_can_be_switched_off(self):
        SystemSetting.objects.filter(key="auto_approve_low_risk").update(value=False)
        self.submit(LOW)
        self.assertEqual(self.pending().level, Approval.Level.STANDARD)

    def test_medium_goes_to_manager_of_same_department_and_is_flagged(self):
        self.submit(MEDIUM)
        approval = self.pending()
        self.assertEqual((approval.level, approval.assigned_to), (Approval.Level.MANAGER, self.manager))
        self.assertEqual(self.invoice.fraud_status, Invoice.FraudStatus.FLAGGED)
        alert = FraudAlert.objects.get(invoice=self.invoice)
        self.assertEqual((alert.severity, alert.primary_type, alert.assigned_to), ("MEDIUM", "SPLIT_PURCHASE", None))
        self.assertTrue(Notification.objects.filter(recipient=self.manager, type="APPROVAL_REQUIRED").exists())

    def test_high_goes_to_auditor_with_assigned_alert(self):
        self.submit(HIGH)
        self.assertEqual((self.pending().level, self.pending().assigned_to), (Approval.Level.AUDITOR, self.auditor))
        self.assertEqual(FraudAlert.objects.get(invoice=self.invoice).assigned_to, self.auditor)
        self.assertTrue(Notification.objects.filter(recipient=self.auditor, type="HIGH_RISK_INVOICE").exists())

    def test_critical_is_blocked(self):
        self.submit(CRITICAL)
        self.assertEqual(self.invoice.approval_status, Status.BLOCKED)
        self.assertFalse(Approval.objects.filter(invoice=self.invoice).exists())
        self.assertEqual(Payment.objects.get(invoice=self.invoice).status, Payment.Status.BLOCKED)
        self.assertTrue(AuditLog.objects.filter(action="INVOICE_BLOCKED").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.ap, type="PAYMENT_BLOCKED").exists())

    def test_ml_service_down_is_fail_safe(self):
        response = self.submit(ml_client.MLServiceError("Cannot reach the ML service"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.invoice.approval_status, Status.UNDER_REVIEW)   # saved and routed, never lost
        self.assertEqual(self.invoice.fraud_status, Invoice.FraudStatus.ANALYSIS_FAILED)
        self.assertEqual(self.pending().level, Approval.Level.MANAGER)
        self.assertTrue(AuditLog.objects.filter(action="FRAUD_ANALYSIS_FAILED").exists())

    def test_low_risk_without_ml_model_is_never_auto_approved(self):
        self.submit(fake_analysis("LOW", 0, [], model_loaded=False))
        self.assertEqual(self.invoice.approval_status, Status.UNDER_REVIEW)
        self.assertEqual(self.pending().level, Approval.Level.MANAGER)
        routed = AuditLog.objects.filter(action="INVOICE_ROUTED").latest("id")
        self.assertIn("ML model unavailable", routed.description)

    def test_submitter_is_never_the_reviewer(self):
        manager_submitter = make_user("MANAGER", department="IT")
        invoice = make_invoice(vendor=self.vendor, submitted_by=manager_submitter, department="IT")
        other_it = [self.manager]
        with mock.patch(ANALYZE, return_value=MEDIUM):
            from approvals.services import submit_invoice
            submit_invoice(invoice, manager_submitter)
        self.assertIn(self.pending(invoice).assigned_to, other_it)

    def test_only_drafts_can_be_submitted(self):
        self.submit(LOW)
        response = self.submit(LOW)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE_TRANSITION")

    def test_roles_that_cannot_submit(self):
        for user in (self.manager, self.auditor):
            with self.subTest(role=user.role_code):
                response = client_for(user).post(f"/api/invoices/{self.invoice.pk}/submit/")
                self.assertEqual(response.status_code, 403)


class DecisionTests(WorkflowTestCase):
    def setUp(self):
        super().setUp()
        self.submit(MEDIUM)
        self.approval = self.pending()
        self.url = f"/api/approvals/{self.approval.pk}"

    def post(self, path, user=None, **body):
        return client_for(user or self.manager).post(f"{self.url}/{path}/", body, format="json")

    def test_queue_shows_only_my_approvals(self):
        mine = client_for(self.manager).get("/api/approvals/?decision=PENDING").json()
        self.assertEqual([row["invoice_number"] for row in mine["results"]], [self.invoice.invoice_number])
        self.assertEqual(client_for(self.other_manager).get("/api/approvals/").json()["count"], 0)
        self.assertEqual(client_for(self.admin).get("/api/approvals/").json()["count"], 1)   # admin sees all
        self.assertEqual(client_for(self.ap).get("/api/approvals/").status_code, 403)

    def test_approve(self):
        response = self.post("approve", comment="Checked with procurement")
        self.assertEqual(response.status_code, 200, response.json())
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.approval_status, self.invoice.fraud_status), (Status.APPROVED, "REVIEWED_CLEARED"))
        self.assertEqual(FraudAlert.objects.get(invoice=self.invoice).status, FraudAlert.Status.DISMISSED)
        self.assertEqual(Payment.objects.get(invoice=self.invoice).status, Payment.Status.SCHEDULED)
        self.assertTrue(Notification.objects.filter(recipient=self.ap, type="INVOICE_APPROVED").exists())
        self.assertTrue(AuditLog.objects.filter(action="INVOICE_APPROVED", user=self.manager).exists())

    def test_only_the_assigned_reviewer_can_decide(self):
        response = self.post("approve", user=self.other_manager)
        self.assertEqual(response.status_code, 404)      # not in their queue at all
        response = client_for(self.auditor).post(f"{self.url}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_cannot_decide_twice(self):
        self.post("approve")
        response = self.post("reject", comment="changed my mind")
        self.assertEqual(response.status_code, 409)

    def test_reject_requires_a_comment(self):
        self.assertEqual(self.post("reject").status_code, 400)
        response = self.post("reject", comment="Duplicate of INV-1001")
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, Status.REJECTED)
        self.assertTrue(Notification.objects.filter(recipient=self.ap, type="INVOICE_REJECTED",
                                                    message="Duplicate of INV-1001").exists())

    def test_clarification_returns_to_draft_and_can_be_resubmitted(self):
        self.assertEqual(self.post("request-clarification").status_code, 400)
        self.post("request-clarification", comment="Please attach the purchase order")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, Status.DRAFT)
        self.assertTrue(Notification.objects.filter(recipient=self.ap, type="CLARIFICATION_REQUESTED").exists())
        # The submitter edits and submits again: a new analysis and a new review.
        client_for(self.ap).patch(f"/api/invoices/{self.invoice.pk}/", {"purchase_order_number": "PO-1"}, format="json")
        self.submit(MEDIUM)
        self.assertEqual(self.invoice.approval_status, Status.UNDER_REVIEW)
        self.assertEqual(FraudAnalysis.objects.filter(invoice=self.invoice).count(), 2)
        self.assertEqual(FraudAlert.objects.filter(invoice=self.invoice).count(), 1)  # the open alert is reused

    def test_escalate_to_auditor(self):
        response = self.post("escalate", comment="Vendor looks suspicious")
        self.assertEqual(response.status_code, 200)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.decision, Approval.Decision.ESCALATED)
        new = self.pending()
        self.assertEqual((new.level, new.assigned_to), (Approval.Level.AUDITOR, self.auditor))
        # auditors decide but cannot escalate further
        self.assertEqual(client_for(self.auditor).post(f"/api/approvals/{new.pk}/escalate/", {"comment": "x"},
                                                       format="json").status_code, 403)
        self.assertEqual(client_for(self.auditor).post(f"/api/approvals/{new.pk}/approve/", {}, format="json").status_code, 200)

    def test_separation_of_duties_in_service(self):
        """Even if roles change later, nobody can approve an invoice they submitted."""
        self.approval.assigned_to = self.ap
        self.approval.save()
        self.ap.role = self.manager.role
        self.ap.save()
        response = client_for(self.ap).post(f"{self.url}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "SELF_APPROVAL")


class PaymentTests(WorkflowTestCase):
    def test_simulate_payment_for_approved_invoice(self):
        self.submit(LOW)
        response = client_for(self.admin).post(f"/api/payments/{self.invoice.pk}/simulate/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["status"], "PAID_SIMULATED")
        self.assertIn("No money is transferred", response.json()["note"])
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, Status.PAID)
        self.assertTrue(AuditLog.objects.filter(action="PAYMENT_SIMULATED").exists())

    def test_only_approved_and_not_blocked(self):
        draft = client_for(self.admin).post(f"/api/payments/{self.invoice.pk}/simulate/")
        self.assertEqual(draft.status_code, 409)
        self.submit(CRITICAL)
        blocked = client_for(self.admin).post(f"/api/payments/{self.invoice.pk}/simulate/")
        self.assertEqual(blocked.status_code, 409)

    def test_only_admin_simulates(self):
        self.submit(LOW)
        self.assertEqual(client_for(self.auditor).post(f"/api/payments/{self.invoice.pk}/simulate/").status_code, 403)
        self.assertEqual(client_for(self.auditor).get("/api/payments/").status_code, 200)
