from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Shape of every error response (same as the Django API)."""

    success: bool = False
    error: ErrorBody


ERROR_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Missing or invalid X-Internal-API-Key"},
    422: {"model": ErrorResponse, "description": "Request body failed validation"},
}
