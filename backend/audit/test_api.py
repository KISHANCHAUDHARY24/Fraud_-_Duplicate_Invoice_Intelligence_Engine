from django.test import TestCase
from rest_framework.test import APIClient

from common.test_utils import make_invoice, make_user

from .models import AuditLog
from .services import log_action


class AuditLogApiTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADMIN")
        self.invoice = make_invoice()
        log_action(AuditLog.Action.INVOICE_APPROVED, user=self.admin, entity=self.invoice, description="approved")
        log_action(AuditLog.Action.SETTINGS_CHANGED, user=self.admin, entity_type="system_setting", entity_id="x")

    def client_for(self, role):
        client = APIClient()
        client.force_authenticate(make_user(role) if isinstance(role, str) else role)
        return client

    def test_only_admin_and_auditor_can_view(self):
        expected = {"ADMIN": 200, "AUDITOR": 200, "MANAGER": 403, "AP_OFFICER": 403}
        for role, status_code in expected.items():
            with self.subTest(role=role):
                self.assertEqual(self.client_for(role).get("/api/audit-logs/").status_code, status_code)

    def test_filter_by_action_and_entity(self):
        client = self.client_for("AUDITOR")
        body = client.get(f"/api/audit-logs/?action=INVOICE_APPROVED&entity_type=invoice&entity_id={self.invoice.pk}").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["action_label"], "Invoice approved")
        self.assertEqual(body["results"][0]["user_name"], str(self.admin))

    def test_audit_log_cannot_be_changed_through_the_api(self):
        client = self.client_for(self.admin)
        entry_id = AuditLog.objects.first().pk
        self.assertEqual(client.post("/api/audit-logs/", {}, format="json").status_code, 405)
        self.assertEqual(client.patch(f"/api/audit-logs/{entry_id}/", {"description": "x"}, format="json").status_code, 405)
        self.assertEqual(client.delete(f"/api/audit-logs/{entry_id}/").status_code, 405)

    def test_actions_list_for_filter_dropdown(self):
        actions = self.client_for("AUDITOR").get("/api/audit-logs/actions/").json()
        self.assertIn({"value": "INVOICE_APPROVED", "label": "Invoice approved"}, actions)

    def test_entity_types_are_distinct(self):
        log_action(AuditLog.Action.INVOICE_SUBMITTED, user=self.admin, entity=self.invoice)   # a second invoice entry
        types = self.client_for("AUDITOR").get("/api/audit-logs/entity-types/").json()
        self.assertEqual(types, [{"value": "invoice", "label": "Invoice"}, {"value": "system_setting", "label": "Setting"}])
