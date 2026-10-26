"""Application configuration loaded from environment variables (.env supported)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# backend/.env takes priority, then a project-root .env
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


class Settings:
    def __init__(self) -> None:
        self.app_name = "ReviewIQ API"
        self.version = "1.0.0"

        # MongoDB
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_db = os.getenv("MONGO_DB", "reviewiq")
        self.mongo_timeout_ms = int(os.getenv("MONGO_TIMEOUT_MS", "3000"))

        # Demo mode: if MongoDB is unreachable, fall back to a temporary in-memory
        # store (mongomock). Nothing is persisted in that mode and the API says so.
        self.demo_mode = _bool("DEMO_MODE", True)
        # Force the in-memory store even if MongoDB is running (used by tests).
        self.force_memory_store = _bool("FORCE_MEMORY_STORE", False)
        # Import the bundled sample dataset at startup when the review collection is empty.
        self.auto_import_sample = _bool("AUTO_IMPORT_SAMPLE", True)

        # Paths
        self.model_dir = _path("MODEL_DIR", BACKEND_DIR / "models")
        self.sample_data_path = _path(
            "SAMPLE_DATA_PATH", PROJECT_ROOT / "data" / "sample" / "customer_reviews_preprocessed.csv"
        )
        self.upload_dir = _path("UPLOAD_DIR", PROJECT_ROOT / "data" / "uploads")
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "25"))

        # Rating -> sentiment rule (rating-derived labels, configurable)
        # rating <= RATING_NEGATIVE_MAX -> negative
        # rating >= RATING_POSITIVE_MIN -> positive
        # anything in between            -> neutral
        self.rating_negative_max = float(os.getenv("RATING_NEGATIVE_MAX", "2"))
        self.rating_positive_min = float(os.getenv("RATING_POSITIVE_MIN", "4"))
        self.rating_min = float(os.getenv("RATING_MIN", "1"))
        self.rating_max = float(os.getenv("RATING_MAX", "5"))

        self.save_predictions = _bool("SAVE_PREDICTIONS", True)

        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]


settings = Settings()
