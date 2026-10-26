"""Shared FastAPI dependencies and singletons."""
from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId
from fastapi import Query

from config import settings
from services.ml import ModelService
from services.olap import Filters

model_service = ModelService(settings.model_dir)


def filter_params(
    brand: list[str] | None = Query(None, description="Brand(s); repeat the parameter for several"),
    product: list[str] | None = Query(None, description="Product name(s)"),
    sentiment: list[str] | None = Query(None, description="positive / neutral / negative / unlabeled"),
    rating: list[float] | None = Query(None, description="Exact rating value(s)"),
    year: list[int] | None = Query(None),
    rating_min: float | None = Query(None, ge=0),
    rating_max: float | None = Query(None, ge=0),
    date_from: date | None = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: date | None = Query(None, description="YYYY-MM-DD (inclusive)"),
    search: str | None = Query(None, max_length=200, description="Case-insensitive text search"),
) -> Filters:
    return Filters(brand=brand or [], product=product or [], sentiment=sentiment or [], rating=rating or [],
                   year=year or [], rating_min=rating_min, rating_max=rating_max,
                   date_from=date_from.isoformat() if date_from else None,
                   date_to=date_to.isoformat() if date_to else None, search=search or None)


def jsonable(doc):
    """Convert Mongo documents (datetimes, ObjectIds) to JSON-friendly values."""
    if isinstance(doc, dict):
        return {k: jsonable(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [jsonable(v) for v in doc]
    if isinstance(doc, datetime):
        # MongoDB stores UTC; pymongo returns naive datetimes, so mark them as UTC explicitly.
        if doc.tzinfo is None:
            doc = doc.replace(tzinfo=timezone.utc)
        return doc.isoformat()
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc
