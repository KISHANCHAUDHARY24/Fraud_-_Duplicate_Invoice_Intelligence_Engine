"""
HTTP client for the FastAPI ML service (docs/architecture.md §5).

Only this module talks to the ML service. Every failure (not running, timeout,
wrong API key, invalid response) becomes MLServiceError, so callers handle one
exception type and can fall back safely.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ANALYZE_PATH = "/api/v1/fraud/analyze"
HEALTH_PATH = "/health"
HEALTH_TIMEOUT_SECONDS = 2


class MLServiceError(Exception):
    """The ML service could not produce a result."""


def _url(path: str) -> str:
    return settings.FASTAPI_URL.rstrip("/") + path


def _headers() -> dict:
    return {"X-Internal-API-Key": settings.ML_SERVICE_API_KEY}


def analyze(payload: dict) -> dict:
    if not settings.ML_SERVICE_API_KEY:
        raise MLServiceError("ML_SERVICE_API_KEY is not configured in backend/.env.")
    try:
        response = requests.post(_url(ANALYZE_PATH), json=payload, headers=_headers(),
                                 timeout=settings.ML_SERVICE_TIMEOUT)
    except requests.Timeout:
        raise MLServiceError(f"The ML service did not answer within {settings.ML_SERVICE_TIMEOUT} seconds.")
    except requests.ConnectionError:
        raise MLServiceError(f"Cannot reach the ML service at {settings.FASTAPI_URL}. Is it running?")

    if response.status_code != 200:
        try:
            message = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = response.text[:200]
        logger.error("ML service returned %s: %s", response.status_code, message)
        raise MLServiceError(f"The ML service rejected the request ({response.status_code}): {message}")

    try:
        result = response.json()
        _ = result["risk_score"], result["risk_level"], result["signals"], result["scoring"]
    except (ValueError, KeyError, TypeError):
        raise MLServiceError("The ML service returned an unexpected response.")
    return result


def health() -> dict | None:
    """Status of the ML service, or None if it cannot be reached (never raises)."""
    try:
        response = requests.get(_url(HEALTH_PATH), timeout=HEALTH_TIMEOUT_SECONDS)
        return response.json() if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None
