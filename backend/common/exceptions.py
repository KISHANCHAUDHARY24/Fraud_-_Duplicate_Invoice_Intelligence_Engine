"""
Consistent error responses for the whole API.

Every error returned by Django REST Framework is converted to:

    {
        "success": false,
        "error": {"code": "VALIDATION_ERROR", "message": "...", "details": {...}}
    }

Unexpected exceptions are logged with their traceback on the server, and the
client only receives a generic SERVER_ERROR message.
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken

logger = logging.getLogger(__name__)


class BusinessError(exceptions.APIException):
    """
    Raise from services for business-rule failures, e.g.
        raise BusinessError("INVALID_STATE_TRANSITION", "Invoice is already approved.", status_code=409)
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BUSINESS_ERROR"

    def __init__(self, code, message, status_code=None, details=None):
        super().__init__(detail=message, code=code)
        self.error_code = code
        self.details = details
        if status_code is not None:
            self.status_code = status_code


# Map DRF exception classes to our public error codes.
# Order matters: subclasses (InvalidToken) must come before their parents.
ERROR_CODES = {
    InvalidToken: "TOKEN_INVALID",
    exceptions.ValidationError: "VALIDATION_ERROR",
    exceptions.NotAuthenticated: "NOT_AUTHENTICATED",
    exceptions.AuthenticationFailed: "AUTHENTICATION_FAILED",
    exceptions.PermissionDenied: "PERMISSION_DENIED",
    exceptions.NotFound: "NOT_FOUND",
    exceptions.MethodNotAllowed: "METHOD_NOT_ALLOWED",
    exceptions.ParseError: "PARSE_ERROR",
    exceptions.UnsupportedMediaType: "UNSUPPORTED_MEDIA_TYPE",
    exceptions.Throttled: "TOO_MANY_REQUESTS",
}


def _first_message(detail):
    """Find the first human-readable message inside a nested DRF error detail."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            if key in ("code", "messages"):  # SimpleJWT internals, not user-facing
                continue
            message = _first_message(value)
            if message:
                return message if key in ("non_field_errors", "detail") else f"{key}: {message}"
    elif isinstance(detail, list):
        for item in detail:
            message = _first_message(item)
            if message:
                return message
    elif detail:
        return str(detail)
    return None


def error_payload(code, message, details=None):
    return {"success": False, "error": {"code": code, "message": message, "details": details}}


def custom_exception_handler(exc, context):
    # Let DRF translate Django's Http404 / PermissionDenied first.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        # Raised by models/services (full_clean, add_bank_account, ...): a 400, not a crash.
        exc = exceptions.ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)

    response = exception_handler(exc, context)

    if response is None:
        # Not an API exception: a bug or infrastructure failure.
        view = context.get("view")
        logger.exception("Unhandled error in %s", view.__class__.__name__ if view else "unknown view")
        return Response(
            error_payload("SERVER_ERROR", "An unexpected error occurred. Please try again later."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, BusinessError):
        code, message, details = exc.error_code, str(exc.detail), exc.details
    else:
        code = next(
            (value for cls, value in ERROR_CODES.items() if isinstance(exc, cls)),
            str(getattr(exc, "default_code", "ERROR")).upper(),
        )
        detail = response.data
        details = detail if isinstance(exc, exceptions.ValidationError) else None
        message = _first_message(detail) or "Request failed."

    if response.status_code >= 500:
        logger.error("API error %s: %s", code, message)

    response.data = error_payload(code, message, details)
    return response
