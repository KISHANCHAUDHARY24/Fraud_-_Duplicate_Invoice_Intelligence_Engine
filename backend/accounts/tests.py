from django.db import IntegrityError
from django.test import TestCase

from common.test_utils import make_user

from .models import Role, User


class RoleSeedTests(TestCase):
    def test_four_roles_are_created_by_migration(self):
        self.assertEqual(
            set(Role.objects.values_list("code", flat=True)),
            {"ADMIN", "AP_OFFICER", "MANAGER", "AUDITOR"},
        )


class UserModelTests(TestCase):
    def test_password_is_hashed_not_stored_in_plain_text(self):
        user = make_user(password="Str0ng!Passw0rd")
        self.assertNotEqual(user.password, "Str0ng!Passw0rd")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password("Str0ng!Passw0rd"))

    def test_has_role(self):
        manager = make_user(Role.Code.MANAGER)
        self.assertTrue(manager.has_role("MANAGER"))
        self.assertTrue(manager.has_role("AUDITOR", "MANAGER"))
        self.assertFalse(manager.has_role("ADMIN"))

    def test_superuser_without_role_counts_as_admin(self):
        admin = User.objects.create_superuser("root", "root@example.com", "Str0ng!Passw0rd")
        self.assertEqual(admin.role_code, "ADMIN")

    def test_user_without_role_has_no_role(self):
        user = User.objects.create_user("plain", "plain@example.com", "Str0ng!Passw0rd")
        self.assertIsNone(user.role_code)
        self.assertFalse(user.has_role("ADMIN"))

    def test_email_must_be_unique(self):
        make_user(email="same@example.com")
        with self.assertRaises(IntegrityError):
            make_user(email="same@example.com")
