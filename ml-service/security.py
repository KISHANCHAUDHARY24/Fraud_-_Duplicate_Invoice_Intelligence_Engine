"""
Service-to-service authentication.

Only Django calls this service. Every request (except /health) must carry
    X-Internal-API-Key: <same value as ML_SERVICE_API_KEY in backend/.env>
The browser never talks to this service directly.
"""

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False, description="Shared secret with Django")


def require_api_key(api_key: str | None = Depends(api_key_header), settings: Settings = Depends(get_settings)) -> None:
    # compare_digest takes the same time for every wrong key, so the key cannot be guessed by timing.
    if not api_key or not hmac.compare_digest(api_key.encode(), settings.internal_api_key.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid internal API key.")
