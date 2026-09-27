"""
Consistent error responses, identical in shape to the Django API:

    {"success": false, "error": {"code": "...", "message": "...", "details": ...}}

Tracebacks are logged on the server and never returned to the caller.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ml_service.errors")

HTTP_CODES = {
    401: "NOT_AUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(status_code, code, message, details=None):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message, "details": details}},
    )


def _field_name(location):
    # ("body", "invoice", "amount") -> "invoice.amount"
    parts = [str(part) for part in location if part not in ("body", "query", "path", "header")]
    return ".".join(parts) or "request"


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [{"field": _field_name(err["loc"]), "message": err["msg"]} for err in exc.errors()]
    first = details[0] if details else {"field": "request", "message": "Invalid request."}
    return error_response(422, "VALIDATION_ERROR", f"{first['field']}: {first['message']}", details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = HTTP_CODES.get(exc.status_code, "ERROR")
    return error_response(exc.status_code, code, str(exc.detail))


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "SERVER_ERROR", "An unexpected error occurred in the ML service.")


def register_error_handlers(app: FastAPI):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
