"""MongoDB connection management with an explicit, clearly-reported demo fallback."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from config import settings

log = logging.getLogger("reviewiq.db")

# Collection names (logical star schema + operational collections)
FACT = "fact_reviews"
DIM_PRODUCT = "dim_product"
DIM_BRAND = "dim_brand"
DIM_DATE = "dim_date"
DIM_SENTIMENT = "dim_sentiment"
DATASETS = "datasets"
ETL_RUNS = "etl_runs"
MODEL_RUNS = "model_runs"
PREDICTIONS = "predictions"

SETUP_MESSAGE = (
    "MongoDB is not reachable at the configured MONGO_URI. Start a local MongoDB server "
    "(e.g. 'net start MongoDB' on Windows) or set MONGO_URI to a MongoDB Atlas connection "
    "string in backend/.env. Alternatively set DEMO_MODE=true to use a temporary in-memory store."
)


class DatabaseState:
    def __init__(self) -> None:
        self.client: Any = None
        self.db: Any = None
        # "mongodb" | "memory" | "unavailable"
        self.mode: str = "unavailable"
        self.error: str | None = None

    @property
    def persistent(self) -> bool:
        return self.mode == "mongodb"

    def info(self) -> dict:
        descriptions = {
            "mongodb": "Connected to MongoDB. Data is persisted.",
            "memory": ("In-memory store forced by FORCE_MEMORY_STORE=true" if settings.force_memory_store
                       else "Demo mode: MongoDB was not reachable, so data is held in a temporary in-memory store")
            + " (mongomock). Data is NOT saved to MongoDB and is lost when the backend stops.",
            "unavailable": SETUP_MESSAGE,
        }
        return {
            "mode": self.mode,
            "persistent": self.persistent,
            "database": settings.mongo_db,
            "description": descriptions[self.mode],
            "error": self.error,
        }


state = DatabaseState()


def _redact(uri: str) -> str:
    if "@" in uri and "://" in uri:
        scheme, rest = uri.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return uri


def connect() -> DatabaseState:
    """Connect to MongoDB, or fall back to an in-memory store if allowed."""
    state.error = None
    if not settings.force_memory_store:
        try:
            client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=settings.mongo_timeout_ms)
            client.admin.command("ping")
            state.client, state.db, state.mode = client, client[settings.mongo_db], "mongodb"
            log.info("Connected to MongoDB at %s (db=%s)", _redact(settings.mongo_uri), settings.mongo_db)
            ensure_indexes(state.db)
            return state
        except PyMongoError as exc:  # pragma: no cover - depends on environment
            state.error = f"{type(exc).__name__}: {str(exc)[:300]}"
            log.warning("MongoDB connection failed: %s", state.error)

    if settings.demo_mode or settings.force_memory_store:
        import mongomock

        client = mongomock.MongoClient()
        state.client, state.db, state.mode = client, client[settings.mongo_db], "memory"
        log.warning("Using the in-memory demo store. Data will NOT be persisted.")
        ensure_indexes(state.db)
    else:
        state.client, state.db, state.mode = None, None, "unavailable"
    return state


def get_db():
    """FastAPI dependency returning the active database or a 503 with setup guidance."""
    if state.db is None:
        raise HTTPException(status_code=503, detail=SETUP_MESSAGE)
    return state.db


def ensure_indexes(db) -> None:
    fact = db[FACT]
    for field in ["sentiment", "brand", "product_name", "rating", "date_key", "year", "year_month",
                  "dataset_id", "product_key", "brand_key"]:
        fact.create_index([(field, ASCENDING)])
    fact.create_index([("brand", ASCENDING), ("sentiment", ASCENDING)])
    fact.create_index([("review_date", DESCENDING)])
    db[ETL_RUNS].create_index([("started_at", DESCENDING)])
    db[MODEL_RUNS].create_index([("trained_at", DESCENDING)])
    db[PREDICTIONS].create_index([("created_at", DESCENDING)])
    db[DATASETS].create_index([("uploaded_at", DESCENDING)])
