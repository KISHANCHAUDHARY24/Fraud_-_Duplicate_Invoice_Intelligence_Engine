from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from approvals.models import Approval
from audit.models import AuditLog
from common.test_utils import make_invoice, make_user, make_vendor
from vendors.services import add_bank_account

from .models import Invoice

Status = Invoice.ApprovalStatus


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def invoice_payload(for_vendor, **overrides):
    payload = {
        "invoice_number": "INV-1001", "vendor": for_vendor.pk, "invoice_date": str(date.today() - timedelta(days=3)),
        "amount": "9900.00", "description": "Office computer equipment",
        "purchase_category": "HARDWARE", "department": "IT",
    }
    payload.update(overrides)
    return payload


class InvoiceCreateTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER", department="Finance")
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.client = client_for(self.ap)

    def test_create_draft_invoice(self):
        account = add_bank_account(self.vendor, "HDFC", "111122223333")
        response = self.client.post("/api/invoices/", invoice_payload(self.vendor, items=[
            {"description": "Laptop", "quantity": "2", "unit_price": "4950.00"}]), format="json")
        self.assertEqual(response.status_code, 201, response.json())
        body = response.json()
        self.assertEqual(body["approval_status"], "DRAFT")
        self.assertEqual(body["fraud_status"], "NOT_ANALYZED")
        self.assertEqual(body["submitted_by"], self.ap.pk)
        self.assertEqual(body["items"][0]["line_total"], "9900.00")
        self.assertEqual(body["payment_bank_account"]["id"], account.pk)  # defaults to vendor's active account
        self.assertIsNone(body["latest_analysis"])
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.INVOICE_CREATED, user=self.ap).exists())

    def test_department_defaults_to_submitter_department(self):
        payload = invoice_payload(self.vendor)
        del payload["department"]
        self.assertEqual(self.client.post("/api/invoices/", payload, format="json").json()["department"], "Finance")

    def test_validation_errors_are_readable(self):
        cases = [
            ({"amount": "0"}, "amount", "Invoice amount must be greater than zero."),
            ({"amount": "-5"}, "amount", "Invoice amount must be greater than zero."),
            ({"amount": "abc"}, "amount", None),
            ({"invoice_date": str(date.today() + timedelta(days=1))}, "invoice_date", "Invoice date cannot be in the future."),
            ({"due_date": str(date.today() - timedelta(days=30))}, "due_date", "Due date cannot be before the invoice date."),
            ({"currency": "DOLLARS"}, "currency", None),
            ({"invoice_number": "   "}, "invoice_number", None),
            ({"description": "x"}, "description", "Description must be at least 3 characters."),
            ({"vendor": 999999}, "vendor", None),
        ]
        for overrides, field, message in cases:
            with self.subTest(overrides=overrides):
                response = self.client.post("/api/invoices/", invoice_payload(self.vendor, **overrides), format="json")
                self.assertEqual(response.status_code, 400)
                error = response.json()["error"]
                self.assertEqual(error["code"], "VALIDATION_ERROR")
                self.assertIn(field, error["details"])
                if message:
                    self.assertIn(message, error["details"][field])

    def test_blocked_vendor_cannot_receive_invoices(self):
        blocked = make_vendor(status="BLOCKED")
        response = self.client.post("/api/invoices/", invoice_payload(blocked), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("vendor", response.json()["error"]["details"])

    def test_bank_account_of_another_vendor_is_rejected(self):
        foreign = add_bank_account(make_vendor(), "HDFC", "999988887777")
        response = self.client.post("/api/invoices/", invoice_payload(self.vendor, payment_bank_account=foreign.pk), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("payment_bank_account", response.json()["error"]["details"])

    def test_exact_duplicate_returns_409(self):
        self.client.post("/api/invoices/", invoice_payload(self.vendor), format="json")
        response = self.client.post("/api/invoices/", invoice_payload(self.vendor), format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "DUPLICATE_INVOICE_NUMBER")
        self.assertIn("existing_invoice_id", response.json()["error"]["details"])

    def test_near_duplicate_is_accepted_for_later_analysis(self):
        self.client.post("/api/invoices/", invoice_payload(self.vendor), format="json")
        response = self.client.post("/api/invoices/", invoice_payload(self.vendor, invoice_number="INV1001"), format="json")
        self.assertEqual(response.status_code, 201)

    def test_roles_without_create_capability_are_forbidden(self):
        for role in ("MANAGER", "AUDITOR"):
            with self.subTest(role=role):
                response = client_for(make_user(role)).post("/api/invoices/", invoice_payload(self.vendor), format="json")
                self.assertEqual(response.status_code, 403)


class InvoiceEditDeleteTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER")
        self.client = client_for(self.ap)
        self.invoice = make_invoice(submitted_by=self.ap, amount=Decimal("100.00"))

    def test_edit_draft_is_audited_with_changes(self):
        response = self.client.patch(f"/api/invoices/{self.invoice.pk}/", {"amount": "150.00"}, format="json")
        self.assertEqual(response.status_code, 200)
        entry = AuditLog.objects.get(action=AuditLog.Action.INVOICE_UPDATED)
        self.assertEqual(entry.old_value, {"amount": "100.00"})
        self.assertEqual(entry.new_value, {"amount": "150.00"})

    def test_submitted_invoice_cannot_be_edited_or_deleted(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(approval_status=Status.UNDER_REVIEW)
        edit = self.client.patch(f"/api/invoices/{self.invoice.pk}/", {"amount": "1"}, format="json")
        delete = self.client.delete(f"/api/invoices/{self.invoice.pk}/")
        self.assertEqual((edit.status_code, delete.status_code), (409, 409))
        self.assertEqual(edit.json()["error"]["code"], "INVOICE_NOT_EDITABLE")

    def test_changing_number_to_existing_one_is_409(self):
        make_invoice(vendor=self.invoice.vendor, submitted_by=self.ap, invoice_number="TAKEN-1")
        response = self.client.patch(f"/api/invoices/{self.invoice.pk}/", {"invoice_number": "TAKEN-1"}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_delete_draft(self):
        self.assertEqual(self.client.delete(f"/api/invoices/{self.invoice.pk}/").status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.INVOICE_DELETED).exists())

    def test_history_lists_audit_entries(self):
        self.client.patch(f"/api/invoices/{self.invoice.pk}/", {"description": "Updated description"}, format="json")
        history = self.client.get(f"/api/invoices/{self.invoice.pk}/history/").json()
        self.assertEqual(history[0]["action"], "INVOICE_UPDATED")


class InvoiceVisibilityTests(TestCase):
    """Object-level security: each role sees only its scope; everything else is a 404."""

    def setUp(self):
        self.ap1, self.ap2 = make_user("AP_OFFICER"), make_user("AP_OFFICER")
        self.manager = make_user("MANAGER", department="IT")
        self.auditor = make_user("AUDITOR")
        self.admin = make_user("ADMIN")
        self.own = make_invoice(submitted_by=self.ap1)
        self.other = make_invoice(submitted_by=self.ap2)
        self.it_submitted = make_invoice(submitted_by=self.ap2, department="IT", approval_status=Status.APPROVED)
        self.it_draft = make_invoice(submitted_by=self.ap2, department="IT")
        self.assigned = make_invoice(submitted_by=self.ap2, department="HR", approval_status=Status.UNDER_REVIEW)
        Approval.objects.create(invoice=self.assigned, level=Approval.Level.MANAGER, assigned_to=self.manager)
        self.high_risk = make_invoice(submitted_by=self.ap2, risk_score=85, risk_level="CRITICAL",
                                      approval_status=Status.BLOCKED)

    def visible_ids(self, user):
        return {row["id"] for row in client_for(user).get("/api/invoices/?page_size=100").json()["results"]}

    def test_ap_officer_sees_only_own_invoices(self):
        self.assertEqual(self.visible_ids(self.ap1), {self.own.pk})

    def test_other_officers_invoice_is_404_not_403(self):
        response = client_for(self.ap1).get(f"/api/invoices/{self.other.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(client_for(self.ap1).patch(f"/api/invoices/{self.other.pk}/", {"amount": "1"}, format="json").status_code, 404)

    def test_manager_sees_assigned_and_submitted_department_invoices(self):
        self.assertEqual(self.visible_ids(self.manager), {self.it_submitted.pk, self.assigned.pk})

    def test_auditor_sees_all_invoices_read_only(self):
        # Oversight role: needs normal invoices to compare with and full vendor history (Phase 9 decision).
        self.assertEqual(len(self.visible_ids(self.auditor)), Invoice.objects.count())
        response = client_for(self.auditor).patch(f"/api/invoices/{self.own.pk}/", {"amount": "1"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_everything(self):
        self.assertEqual(len(self.visible_ids(self.admin)), Invoice.objects.count())


class InvoiceListTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADMIN")
        self.client = client_for(self.admin)
        self.acme = make_vendor(vendor_name="ACME Corp")
        make_invoice(vendor=self.acme, invoice_number="A-1", amount=Decimal("500"), invoice_date=date(2026, 8, 1))
        make_invoice(vendor=self.acme, invoice_number="A-2", amount=Decimal("9900"), invoice_date=date(2026, 9, 1),
                     risk_score=70, risk_level="HIGH", approval_status=Status.UNDER_REVIEW)
        make_invoice(invoice_number="B-1", amount=Decimal("20000"), invoice_date=date(2026, 9, 10),
                     risk_score=10, risk_level="LOW", approval_status=Status.APPROVED)

    def numbers(self, query):
        response = self.client.get(f"/api/invoices/?{query}")
        self.assertEqual(response.status_code, 200, response.json())
        return [row["invoice_number"] for row in response.json()["results"]]

    def test_filters(self):
        self.assertEqual(self.numbers(f"vendor={self.acme.pk}&ordering=invoice_number"), ["A-1", "A-2"])
        self.assertEqual(self.numbers("amount_min=1000&amount_max=10000"), ["A-2"])
        self.assertEqual(self.numbers("date_from=2026-09-01&date_to=2026-09-05"), ["A-2"])
        self.assertEqual(self.numbers("risk_level=HIGH,CRITICAL"), ["A-2"])
        self.assertEqual(self.numbers("approval_status=UNDER_REVIEW,APPROVED&ordering=invoice_number"), ["A-2", "B-1"])

    def test_search_and_sort(self):
        self.assertEqual(self.numbers("search=acme&ordering=-amount"), ["A-2", "A-1"])
        self.assertEqual(self.numbers("ordering=-risk_score")[0], "A-2")

    def test_pagination(self):
        body = self.client.get("/api/invoices/?page_size=2").json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(len(body["results"]), 2)
        self.assertIsNotNone(body["next"])

    def test_invalid_filter_value_is_400(self):
        response = self.client.get("/api/invoices/?date_from=not-a-date")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
