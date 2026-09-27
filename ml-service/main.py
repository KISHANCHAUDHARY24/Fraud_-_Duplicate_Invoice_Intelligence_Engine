"""
Expense Intelligence ML service (FastAPI).

Run (from the ml-service folder, venv active):
    uvicorn main:app --reload --port 8001
Interactive API docs: http://127.0.0.1:8001/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import SERVICE_VERSION, get_settings
from errors import register_error_handlers
from routers import duplicate, fraud, health, risk, vendor
from services.anomaly_detector import detector


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()  # fail fast at startup if INTERNAL_API_KEY is missing
    logging.basicConfig(level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logging.getLogger("ml_service").info("ML service %s started", SERVICE_VERSION)
    detector.load(settings.model_dir)   # once per process, never per request
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Expense Intelligence ML Service",
        version=SERVICE_VERSION,
        description=(
            "Duplicate detection, fraud rules, anomaly detection and explainable risk scoring for invoices.\n\n"
            "**Called only by the Django backend.** Every endpoint except `/health` needs the "
            "`X-Internal-API-Key` header (use the **Authorize** button).\n\n"
            "Results are *risk indicators* for human review, never a determination of fraud."
        ),
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(duplicate.router)
    app.include_router(fraud.router)
    app.include_router(vendor.router)
    app.include_router(risk.router)
    return app


app = create_app()
