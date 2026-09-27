"""User and role management API: Admin only, audited, no hard deletes."""

from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import make_user

from .models import User


class UserManagementApiTests(TestCase):
    def setUp(self):
        self.admin = make_user("ADMIN", username="admin1")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_non_admin_roles_are_forbidden(self):
        for role in ("AP_OFFICER", "MANAGER", "AUDITOR"):
            with self.subTest(role=role):
                client = APIClient()
                client.force_authenticate(make_user(role))
                for response in (client.get("/api/users/"), client.get("/api/roles/"),
                                 client.post("/api/users/", {}, format="json")):
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()["error"]["code"], "PERMISSION_DENIED")

    def test_list_users_is_paginated_and_filterable(self):
        make_user("MANAGER", username="mgr1")
        response = self.client.get("/api/users/?role=MANAGER")
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["username"], "mgr1")

    def test_create_user(self):
        response = self.client.post("/api/users/", {
            "username": "newmgr", "email": "newmgr@example.com", "first_name": "New",
            "last_name": "Manager", "role": "MANAGER", "department": "IT", "password": "Str0ng!Passw0rd",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["role"], "MANAGER")
        self.assertNotIn("password", response.json())
        user = User.objects.get(username="newmgr")
        self.assertTrue(user.check_password("Str0ng!Passw0rd"))
        entry = AuditLog.objects.get(action=AuditLog.Action.USER_CREATED)
        self.assertEqual(entry.user, self.admin)
        self.assertNotIn("Str0ng!Passw0rd", str(entry.new_value))

    def test_create_user_rejects_weak_password_and_unknown_role(self):
        response = self.client.post("/api/users/", {
            "username": "weak", "email": "weak@example.com", "role": "CEO", "password": "weak",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json()["error"]["details"])

    def test_role_change_is_audited_with_old_and_new_values(self):
        user = make_user("AP_OFFICER")
        response = self.client.patch(f"/api/users/{user.pk}/", {"role": "AUDITOR"}, format="json")
        self.assertEqual(response.status_code, 200)
        entry = AuditLog.objects.get(action=AuditLog.Action.ROLE_CHANGED)
        self.assertEqual(entry.old_value, {"role": "AP_OFFICER"})
        self.assertEqual(entry.new_value, {"role": "AUDITOR"})

    def test_users_cannot_be_deleted(self):
        user = make_user()
        self.assertEqual(self.client.delete(f"/api/users/{user.pk}/").status_code, 405)

    def test_deactivate_and_reactivate(self):
        user = make_user()
        response = self.client.post(f"/api/users/{user.pk}/deactivate/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_active"])
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.USER_DEACTIVATED).exists())
        self.assertTrue(self.client.post(f"/api/users/{user.pk}/activate/").json()["is_active"])

    def test_admin_cannot_deactivate_self(self):
        response = self.client.post(f"/api/users/{self.admin.pk}/deactivate/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "CANNOT_DEACTIVATE_SELF")

    def test_roles_list(self):
        response = self.client.get("/api/roles/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 4)
