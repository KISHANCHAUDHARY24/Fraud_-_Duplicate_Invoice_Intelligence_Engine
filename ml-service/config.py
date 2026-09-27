"""Service configuration, read once from environment variables (ml-service/.env)."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SERVICE_NAME = "expense-intelligence-ml-service"
SERVICE_VERSION = "0.1.0"


@dataclass(frozen=True)
class Settings:
    internal_api_key: str
    model_dir: Path
    log_level: str


@lru_cache
def get_settings() -> Settings:
    api_key = os.environ.get("INTERNAL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY is not set. Copy ml-service/.env.example to ml-service/.env "
            "and use the same value as ML_SERVICE_API_KEY in backend/.env."
        )
    model_dir = Path(os.environ.get("MODEL_DIR", "models"))
    return Settings(
        internal_api_key=api_key,
        model_dir=model_dir if model_dir.is_absolute() else BASE_DIR / model_dir,
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )
