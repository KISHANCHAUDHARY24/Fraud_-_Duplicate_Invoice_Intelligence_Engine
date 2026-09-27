from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import make_user

from .defaults import DEFAULT_SETTINGS
from .services import get_setting


class SettingsApiTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADMIN")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def patch(self, key, value, client=None):
        return (client or self.client).patch(f"/api/settings/{key}/", {"value": value}, format="json")

    def test_view_permissions(self):
        expected = {"ADMIN": 200, "MANAGER": 200, "AUDITOR": 200, "AP_OFFICER": 403}
        for role, status_code in expected.items():
            with self.subTest(role=role):
                client = APIClient()
                client.force_authenticate(make_user(role))
                self.assertEqual(client.get("/api/settings/").status_code, status_code)

    def test_list_contains_every_setting_with_default(self):
        rows = self.client.get("/api/settings/").json()
        self.assertEqual({row["key"] for row in rows}, set(DEFAULT_SETTINGS))
        threshold = next(row for row in rows if row["key"] == "approval_threshold")
        self.assertEqual(threshold["default"], 10000)

    def test_only_admin_can_change(self):
        manager = APIClient()
        manager.force_authenticate(make_user("MANAGER"))
        self.assertEqual(self.patch("approval_threshold", 20000, client=manager).status_code, 403)

    def test_change_is_applied_and_audited(self):
        response = self.patch("approval_threshold", 25000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_setting("approval_threshold"), 25000)
        entry = AuditLog.objects.get(action=AuditLog.Action.SETTINGS_CHANGED)
        self.assertEqual((entry.entity_id, entry.old_value, entry.new_value),
                         ("approval_threshold", {"value": 10000}, {"value": 25000}))

    def test_invalid_values_are_rejected_with_reasons(self):
        cases = [
            ("approval_threshold", 0),
            ("approval_threshold", "lots"),
            ("auto_approve_low_risk", "yes"),
            ("duplicate_threshold", 150),
            ("duplicate_weights", {"invoice_number": 0.5, "vendor": 0.5, "amount": 0.5, "date": 0, "description": 0}),
            ("duplicate_weights", {"invoice_number": 1.0}),
            ("working_hours", {"start": "19:00", "end": "08:00"}),
            ("working_hours", {"start": "8am", "end": "5pm"}),
            ("working_days", [0, 0, 1]),
            ("working_days", [7]),
            ("timezone", "Mars/Olympus"),
            ("risk_level_thresholds", {"medium": 60, "high": 30, "critical": 80}),
            ("signal_weights", {"DUPLICATE": 30}),
            ("ml_anomaly_threshold", 1.5),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                response = self.patch(key, value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("value", response.json()["error"]["details"])
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.SETTINGS_CHANGED).exists())

    def test_valid_complex_values(self):
        self.assertEqual(self.patch("working_days", [5, 0, 1, 2, 3, 4]).json()["value"], [0, 1, 2, 3, 4, 5])
        self.assertEqual(self.patch("timezone", "Europe/London").status_code, 200)
        weights = {"invoice_number": 0.4, "vendor": 0.2, "amount": 0.2, "date": 0.1, "description": 0.1}
        self.assertEqual(self.patch("duplicate_weights", weights).status_code, 200)

    def test_reset_to_default(self):
        self.patch("split_window_days", 14)
        response = self.client.post("/api/settings/split_window_days/reset/")
        self.assertEqual(response.json()["value"], 7)

    def test_unknown_key_is_404(self):
        self.assertEqual(self.client.get("/api/settings/not_a_setting/").status_code, 404)
