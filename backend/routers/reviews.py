"""Review search, filtering and pagination."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from db import FACT, get_db
from deps import filter_params, jsonable
from services.olap import Filters, build_match

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])

SORT_FIELDS = {"date": "review_date", "rating": "rating", "product": "product_name", "brand": "brand",
               "length": "review_length", "sentiment": "sentiment"}
LIST_PROJECTION = {"cleaned_review": 0, "product_key": 0, "brand_key": 0, "sentiment_key": 0}


@router.get("", summary="Search, filter, sort and paginate reviews")
def list_reviews(filters: Filters = Depends(filter_params), page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=200),
                 sort: str = Query("date", description="date | rating | product | brand | length | sentiment"),
                 order: str = Query("desc", pattern="^(asc|desc)$"), db=Depends(get_db)):
    if sort not in SORT_FIELDS:
        raise HTTPException(422, f"sort must be one of {', '.join(SORT_FIELDS)}")
    match = build_match(filters)
    total = db[FACT].count_documents(match)
    direction = -1 if order == "desc" else 1
    cursor = (db[FACT].find(match, LIST_PROJECTION)
              .sort([(SORT_FIELDS[sort], direction), ("_id", 1)])
              .skip((page - 1) * page_size).limit(page_size))
    items = list(cursor)
    return {"items": jsonable(items), "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size, "filters": filters.describe()}


@router.get("/filters", summary="Available filter values (brands, products, years, ratings, date range)")
def filter_options(db=Depends(get_db)):
    fact = db[FACT]
    dates = [d for d in fact.distinct("review_date") if d]
    return {
        "brands": sorted(b for b in fact.distinct("brand") if b),
        "products": sorted(p for p in fact.distinct("product_name") if p),
        "years": sorted(y for y in fact.distinct("year") if y is not None),
        "ratings": sorted(r for r in fact.distinct("rating") if r is not None),
        "sentiments": ["positive", "neutral", "negative", "unlabeled"],
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
    }


@router.get("/{review_id}", summary="One review by id")
def get_review(review_id: str, db=Depends(get_db)):
    doc = db[FACT].find_one({"_id": review_id})
    if not doc:
        raise HTTPException(404, "Review not found.")
    return jsonable(doc)
