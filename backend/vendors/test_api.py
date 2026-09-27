from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import make_invoice, make_user, make_vendor
from invoices.models import Invoice
from notifications.models import Notification

from .models import Vendor
from .services import add_bank_account


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class VendorApiTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADMIN")
        self.ap = make_user("AP_OFFICER")
        self.manager = make_user("MANAGER")
        self.auditor = make_user("AUDITOR")

    def test_every_role_can_list_vendors(self):
        make_vendor(vendor_name="ACME Corp")
        for user in (self.admin, self.ap, self.manager, self.auditor):
            with self.subTest(role=user.role_code):
                response = client_for(user).get("/api/vendors/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 1)

    def test_create_vendor_with_first_bank_account(self):
        response = client_for(self.ap).post("/api/vendors/", {
            "vendor_name": "ACME Corp", "registration_number": "REG-1", "email": "ap@acme.test",
            "bank_name": "HDFC Bank", "account_number": "1234 5678 9012",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        body = response.json()
        self.assertEqual(body["active_bank_account"], {"bank_name": "HDFC Bank", "masked_account": "****9012"})
        self.assertNotIn("123456789012", response.content.decode())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.VENDOR_CREATED).exists())

    def test_equivalent_vendor_name_is_rejected(self):
        make_vendor(vendor_name="ACME Corp")
        response = client_for(self.admin).post("/api/vendors/", {"vendor_name": "ACME Corporation"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "VENDOR_ALREADY_EXISTS")

    def test_manager_and_auditor_cannot_create_vendors(self):
        for user in (self.manager, self.auditor):
            with self.subTest(role=user.role_code):
                response = client_for(user).post("/api/vendors/", {"vendor_name": "New Co"}, format="json")
                self.assertEqual(response.status_code, 403)

    def test_only_admin_can_edit_vendor_and_changes_are_audited(self):
        vendor = make_vendor(vendor_name="Old Name Ltd")
        self.assertEqual(client_for(self.ap).patch(f"/api/vendors/{vendor.pk}/", {"status": "BLOCKED"}, format="json").status_code, 403)
        response = client_for(self.admin).patch(f"/api/vendors/{vendor.pk}/", {"status": "BLOCKED"}, format="json")
        self.assertEqual(response.status_code, 200)
        entry = AuditLog.objects.get(action=AuditLog.Action.VENDOR_UPDATED)
        self.assertEqual(entry.old_value, {"status": "ACTIVE"})
        self.assertEqual(entry.new_value, {"status": "BLOCKED"})

    def test_bank_details_cannot_be_changed_through_vendor_edit(self):
        vendor = make_vendor()
        response = client_for(self.admin).patch(f"/api/vendors/{vendor.pk}/", {
            "bank_name": "X", "account_number": "99998888777"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_vendor_with_invoices_cannot_be_deleted(self):
        vendor = make_vendor()
        make_invoice(vendor=vendor)
        response = client_for(self.admin).delete(f"/api/vendors/{vendor.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "VENDOR_HAS_INVOICES")

    def test_vendor_without_invoices_can_be_deleted(self):
        vendor = make_vendor()
        self.assertEqual(client_for(self.admin).delete(f"/api/vendors/{vendor.pk}/").status_code, 204)
        self.assertFalse(Vendor.objects.filter(pk=vendor.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.VENDOR_DELETED).exists())

    def test_bank_account_change_admin_only_and_notifies_auditors(self):
        vendor = make_vendor(vendor_name="ACME Corp")
        add_bank_account(vendor, "HDFC Bank", "111122223333")
        url = f"/api/vendors/{vendor.pk}/bank-accounts/"
        self.assertEqual(client_for(self.ap).post(url, {"bank_name": "X", "account_number": "444455556666"}, format="json").status_code, 403)

        response = client_for(self.admin).post(url, {"bank_name": "ICICI Bank", "account_number": "444455556666"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["masked_account"], "****6666")
        self.assertTrue(Notification.objects.filter(recipient=self.auditor, type=Notification.Type.VENDOR_RISK_ALERT).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.admin).exists())  # the actor is not notified

        history = client_for(self.ap).get(url).json()
        self.assertEqual([a["is_active"] for a in history], [True, False])
        self.assertNotIn("account_hash", history[0])

    def test_invalid_bank_account_number_is_a_400_not_a_crash(self):
        vendor = make_vendor()
        response = client_for(self.admin).post(f"/api/vendors/{vendor.pk}/bank-accounts/",
                                               {"bank_name": "HDFC", "account_number": "12"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("account_number", response.json()["error"]["details"])

    def test_dashboard_totals_and_scoped_recent_invoices(self):
        vendor = make_vendor(vendor_name="ACME Corp")
        other_ap = make_user("AP_OFFICER")
        mine = make_invoice(vendor=vendor, submitted_by=self.ap, amount=Decimal("1000"), approval_status=Invoice.ApprovalStatus.APPROVED)
        make_invoice(vendor=vendor, submitted_by=other_ap, amount=Decimal("3000"), approval_status=Invoice.ApprovalStatus.APPROVED)
        make_invoice(vendor=vendor, submitted_by=self.ap, amount=Decimal("500"))  # draft: not spending

        body = client_for(self.ap).get(f"/api/vendors/{vendor.pk}/dashboard/").json()
        self.assertEqual(body["total_invoices"], 3)
        self.assertEqual(Decimal(body["total_spending"]), Decimal("4000"))
        self.assertEqual(Decimal(body["average_invoice"]), Decimal("2000.00"))
        self.assertEqual({row["id"] for row in body["recent_invoices"]} & {mine.pk}, {mine.pk})
        self.assertEqual(len(body["recent_invoices"]), 2)  # other officer's invoice hidden

    def test_dashboard_reports_recent_bank_change(self):
        vendor = make_vendor()
        add_bank_account(vendor, "HDFC Bank", "111122223333")
        add_bank_account(vendor, "ICICI Bank", "444455556666")
        indicators = client_for(self.auditor).get(f"/api/vendors/{vendor.pk}/dashboard/").json()["risk_indicators"]
        self.assertTrue(any("Bank account changed" in text for text in indicators))

    def test_dashboard_bank_history_needs_bank_capability(self):
        vendor = make_vendor()
        add_bank_account(vendor, "HDFC Bank", "111122223333")
        self.assertEqual(len(client_for(self.auditor).get(f"/api/vendors/{vendor.pk}/dashboard/").json()["bank_accounts"]), 1)
        self.assertEqual(client_for(self.manager).get(f"/api/vendors/{vendor.pk}/dashboard/").json()["bank_accounts"], [])

    def test_list_search_and_filter(self):
        make_vendor(vendor_name="ACME Corp")
        make_vendor(vendor_name="Global Ltd", status=Vendor.Status.BLOCKED)
        client = client_for(self.admin)
        self.assertEqual(client.get("/api/vendors/?search=acme").json()["count"], 1)
        self.assertEqual(client.get("/api/vendors/?status=BLOCKED").json()["results"][0]["vendor_name"], "Global Ltd")
