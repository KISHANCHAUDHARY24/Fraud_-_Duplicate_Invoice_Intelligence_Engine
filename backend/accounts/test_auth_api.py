"""Authentication API tests: login, refresh, logout, me, change-password."""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import make_user

PASSWORD = "Str0ng!Passw0rd"


class AuthApiTestCase(TestCase):
    def setUp(self):
        cache.clear()  # reset the login rate limiter between tests
        self.client = APIClient()
        self.user = make_user("AP_OFFICER", username="asha", password=PASSWORD, first_name="Asha", last_name="Patel")

    def login(self, username="asha", password=PASSWORD):
        return self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")

    def authenticate(self):
        tokens = self.login().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return tokens


class LoginTests(AuthApiTestCase):
    def test_login_returns_tokens_and_user_with_permissions(self):
        response = self.login()
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        self.assertEqual(body["user"]["username"], "asha")
        self.assertEqual(body["user"]["role"], "AP_OFFICER")
        self.assertEqual(body["user"]["full_name"], "Asha Patel")
        self.assertIn("invoices.create", body["user"]["permissions"])
        self.assertNotIn("password", body["user"])

    def test_login_is_audited_and_updates_last_login(self):
        self.login()
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.USER_LOGIN, user=self.user).exists())

    def test_wrong_password_and_unknown_user_give_identical_errors(self):
        wrong_password = self.login(password="nope")
        unknown_user = self.login(username="ghost")
        for response in (wrong_password, unknown_user):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"]["code"], "INVALID_CREDENTIALS")
        self.assertEqual(wrong_password.json(), unknown_user.json())

    def test_failed_login_is_audited_without_the_password(self):
        self.login(password="MySecretGuess1")
        entry = AuditLog.objects.get(action=AuditLog.Action.USER_LOGIN_FAILED)
        self.assertIn("asha", entry.description)
        self.assertNotIn("MySecretGuess1", entry.description)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 401)

    def test_missing_fields_are_a_validation_error(self):
        response = self.client.post("/api/auth/login/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_login_is_rate_limited(self):
        statuses = [self.login(password="wrong").status_code for _ in range(11)]
        self.assertEqual(statuses[-1], 429)
        self.assertEqual(self.login().json()["error"]["code"], "TOO_MANY_REQUESTS")


class TokenTests(AuthApiTestCase):
    def test_protected_endpoint_requires_token(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "NOT_AUTHENTICATED")

    def test_me_with_valid_token(self):
        self.authenticate()
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "asha")

    def test_garbage_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.token")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "TOKEN_INVALID")

    def test_refresh_rotates_and_old_refresh_token_stops_working(self):
        tokens = self.login().json()
        first = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertIn("access", first.json())
        self.assertNotEqual(first.json()["refresh"], tokens["refresh"])

        reused = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(reused.status_code, 401)

    def test_access_token_cannot_be_used_as_refresh_token(self):
        tokens = self.login().json()
        response = self.client.post("/api/auth/refresh/", {"refresh": tokens["access"]}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_deactivated_user_is_locked_out_immediately(self):
        self.authenticate()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)


class LogoutTests(AuthApiTestCase):
    def test_logout_blacklists_refresh_token(self):
        tokens = self.authenticate()
        response = self.client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.USER_LOGOUT).exists())

        refresh = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)

    def test_cannot_log_out_someone_elses_token(self):
        make_user(username="other", password=PASSWORD)
        other_tokens = self.login(username="other").json()
        self.authenticate()
        response = self.client.post("/api/auth/logout/", {"refresh": other_tokens["refresh"]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_logout_with_invalid_token(self):
        self.authenticate()
        response = self.client.post("/api/auth/logout/", {"refresh": "garbage"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "TOKEN_INVALID")


class ChangePasswordTests(AuthApiTestCase):
    NEW = "An0ther!Passw0rd"

    def change(self, old=PASSWORD, new=NEW):
        return self.client.post("/api/auth/change-password/", {"old_password": old, "new_password": new}, format="json")

    def test_change_password_success(self):
        old_tokens = self.authenticate()
        response = self.change()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.PASSWORD_CHANGED).exists())
        # old refresh token (e.g. on another device) no longer works
        refresh = self.client.post("/api/auth/refresh/", {"refresh": old_tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)
        # new password works, old does not
        self.client.credentials()
        self.assertEqual(self.login(password=self.NEW).status_code, 200)
        self.assertEqual(self.login(password=PASSWORD).status_code, 401)

    def test_wrong_old_password(self):
        self.authenticate()
        response = self.change(old="wrong")
        self.assertEqual(response.status_code, 400)
        self.assertIn("old_password", response.json()["error"]["details"])

    def test_weak_new_password_is_rejected(self):
        self.authenticate()
        response = self.change(new="12345678")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
