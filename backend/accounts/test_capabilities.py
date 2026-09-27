"""Permission-matrix tests (docs/authentication.md §4). No database needed."""

from django.test import SimpleTestCase

from .capabilities import ROLE_CAPABILITIES, Cap, capabilities_for, user_can
from .models import Role, User


def user_with(role_code, **fields):
    return User(username="u", role=Role(code=role_code, name=role_code), **fields)


class CapabilityMatrixTests(SimpleTestCase):
    def test_every_role_has_an_entry(self):
        self.assertEqual(set(ROLE_CAPABILITIES), {code for code, _ in Role.Code.choices})

    def test_every_capability_is_declared(self):
        declared = {value for name, value in vars(Cap).items() if name.isupper()}
        for role, caps in ROLE_CAPABILITIES.items():
            with self.subTest(role=role):
                self.assertLessEqual(caps, declared)

    def test_matrix_matches_documentation(self):
        expectations = [
            # (role, capability, allowed)
            ("ADMIN", Cap.USERS_MANAGE, True),
            ("ADMIN", Cap.SETTINGS_MANAGE, True),
            ("ADMIN", Cap.APPROVALS_DECIDE, False),
            ("AP_OFFICER", Cap.INVOICES_CREATE, True),
            ("AP_OFFICER", Cap.APPROVALS_DECIDE, False),
            ("AP_OFFICER", Cap.AUDIT_VIEW, False),
            ("AP_OFFICER", Cap.USERS_MANAGE, False),
            ("MANAGER", Cap.APPROVALS_DECIDE, True),
            ("MANAGER", Cap.APPROVALS_ESCALATE, True),
            ("MANAGER", Cap.INVOICES_CREATE, False),
            ("MANAGER", Cap.AUDIT_VIEW, False),
            ("AUDITOR", Cap.ALERTS_RESOLVE, True),
            ("AUDITOR", Cap.AUDIT_VIEW, True),
            ("AUDITOR", Cap.APPROVALS_ESCALATE, False),
            ("AUDITOR", Cap.SETTINGS_MANAGE, False),
        ]
        for role, capability, allowed in expectations:
            with self.subTest(role=role, capability=capability):
                self.assertEqual(user_can(user_with(role), capability), allowed)

    def test_only_admin_manages_users_and_settings(self):
        for role, caps in ROLE_CAPABILITIES.items():
            with self.subTest(role=role):
                self.assertEqual(Cap.USERS_MANAGE in caps, role == "ADMIN")
                self.assertEqual(Cap.SETTINGS_MANAGE in caps, role == "ADMIN")

    def test_inactive_user_has_no_capabilities(self):
        self.assertEqual(capabilities_for(user_with("ADMIN", is_active=False)), frozenset())

    def test_user_without_role_has_no_capabilities(self):
        self.assertEqual(capabilities_for(User(username="nobody")), frozenset())

    def test_superuser_without_role_gets_admin_capabilities(self):
        root = User(username="root", is_superuser=True)
        self.assertEqual(capabilities_for(root), ROLE_CAPABILITIES["ADMIN"])
