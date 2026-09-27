from decimal import Decimal
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework import serializers
from rest_framework.test import APIClient
from rest_framework.views import APIView

from .exceptions import BusinessError


class _ValidatingView(APIView):
    permission_classes = []
    authentication_classes = []

    class _Serializer(serializers.Serializer):
        amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    def post(self, request):
        self._Serializer(data=request.data).is_valid(raise_exception=True)
        return None


class _BusinessErrorView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        raise BusinessError("INVALID_STATE_TRANSITION", "Invoice is already approved.", status_code=409)


class _CrashView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        raise RuntimeError("secret internal detail")


class _PrivateView(APIView):
    def get(self, request):
        return None


urlpatterns = [
    path("validate/", _ValidatingView.as_view()),
    path("business/", _BusinessErrorView.as_view()),
    path("crash/", _CrashView.as_view()),
    path("private/", _PrivateView.as_view()),
]


class HealthEndpointTests(TestCase):
    ML_UP = {"status": "ok", "model_loaded": True, "model_version": "iforest-test"}

    def setUp(self):
        self.client = APIClient()

    def test_health_ok_when_database_and_ml_service_reachable(self):
        with mock.patch("common.views.ml_client.health", return_value=self.ML_UP):
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok", "ml_service": {
            "status": "ok", "model_loaded": True, "model_version": "iforest-test"}})

    def test_ml_service_down_is_degraded_but_still_200(self):
        # Django keeps working without the ML service (invoices go to manual review).
        with mock.patch("common.views.ml_client.health", return_value=None):
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")
        self.assertEqual(response.json()["ml_service"], {"status": "unavailable"})

    def test_health_503_when_database_down(self):
        with (
            mock.patch("common.views.connection.cursor", side_effect=DatabaseError),
            mock.patch("common.views.ml_client.health", return_value=self.ML_UP),
            self.assertLogs("common.views", level="ERROR"),
        ):
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unavailable")


@override_settings(ROOT_URLCONF="common.tests")
class ErrorFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_validation_error_shape(self):
        response = self.client.post("/validate/", {"amount": "-5"}, format="json")
        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("amount", body["error"]["message"])
        self.assertIn("amount", body["error"]["details"])

    def test_business_error_shape(self):
        response = self.client.get("/business/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE_TRANSITION")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/private/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "NOT_AUTHENTICATED")

    def test_unhandled_error_hides_internal_details(self):
        with self.assertLogs("common.exceptions", level="ERROR"):
            response = self.client.get("/crash/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "SERVER_ERROR")
        self.assertNotIn("secret internal detail", response.content.decode())
