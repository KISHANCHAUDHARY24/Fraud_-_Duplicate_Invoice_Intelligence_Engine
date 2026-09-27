from fastapi import APIRouter

from config import SERVICE_NAME, SERVICE_VERSION
from services.anomaly_detector import detector

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check (no API key needed)")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "model_loaded": detector.loaded,
        "model_version": detector.version,
    }
