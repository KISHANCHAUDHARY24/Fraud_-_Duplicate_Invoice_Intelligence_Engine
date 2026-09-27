import logging

from django.db import DatabaseError, connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fraud import ml_client

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """
    GET /api/health/: public liveness check.

    503 only when the database is down (nothing works without it). If only the ML service
    is down, Django still works (invoices are routed to manual review), so the answer is
    200 with status "degraded".
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = "ok"
        except DatabaseError:
            logger.exception("Health check: database unreachable")
            database = "unavailable"

        ml = ml_client.health()
        ml_service = {"status": "ok", "model_loaded": ml.get("model_loaded"), "model_version": ml.get("model_version")} \
            if ml else {"status": "unavailable"}

        healthy = database == "ok" and ml_service["status"] == "ok"
        return Response(
            {"status": "ok" if healthy else "degraded", "database": database, "ml_service": ml_service},
            status=200 if database == "ok" else 503,
        )
