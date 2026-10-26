"""Dashboard statistics and filterable sentiment analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from db import DATASETS, ETL_RUNS, FACT, MODEL_RUNS, PREDICTIONS, get_db, state
from deps import filter_params, jsonable, model_service
from services.olap import Filters, cube

router = APIRouter(prefix="/api", tags=["Dashboard & Analytics"])


def _labels_row(row: dict) -> dict:
    return {k: row[k] for k in ["positive", "neutral", "negative", "unlabeled"]}


@router.get("/dashboard/stats", summary="Headline numbers, distributions and recent activity")
def dashboard_stats(db=Depends(get_db)):
    total = db[FACT].count_documents({})
    overall = cube(db, [])["rows"]
    overall = overall[0] if overall else None
    by_rating = cube(db, ["rating"])["rows"]
    trend = cube(db, ["month"])["rows"]
    trend = [r for r in trend if r["month"] != "Unknown"][-24:]
    top_products = cube(db, ["product"], sort_by="count", limit=8)["rows"]

    meta = model_service.metadata
    model_summary = None
    if meta:
        best = meta["best_model"]
        model_summary = {"best_model": meta["results"][best]["name"], "trained_at": meta["trained_at"],
                         "f1_macro": meta["results"][best]["f1_macro"],
                         "accuracy": meta["results"][best]["accuracy"],
                         "baseline_accuracy": meta["baseline"]["accuracy"]}

    activity = []
    for r in db[ETL_RUNS].find().sort("started_at", -1).limit(5):
        activity.append({"type": "etl", "at": r["started_at"], "status": r.get("status"),
                         "text": f"ETL ({r.get('source')}): {r.get('load', {}).get('inserted', 0)} reviews loaded, "
                                 f"{r.get('load', {}).get('duplicates_already_in_db', 0)} duplicates skipped"})
    for r in db[MODEL_RUNS].find({}, {"trained_at": 1, "best_model": 1, "results": 1}).sort("trained_at", -1).limit(5):
        best = r["best_model"]
        activity.append({"type": "training", "at": r["trained_at"], "status": "success",
                         "text": f"Models trained — best: {r['results'][best]['name']} "
                                 f"(macro F1 {r['results'][best]['f1_macro']:.3f})"})
    for r in db[PREDICTIONS].find().sort("created_at", -1).limit(5):
        first = next(iter(r["predictions"].values()))
        activity.append({"type": "prediction", "at": r["created_at"], "status": first["label"],
                         "text": f"Predicted '{first['label']}' for: {r['text'][:70]}"})
    activity.sort(key=lambda a: a["at"], reverse=True)

    return jsonable({
        "storage": state.info(),
        "total_reviews": total,
        "sentiment": _labels_row(overall) if overall else {"positive": 0, "neutral": 0, "negative": 0, "unlabeled": 0},
        "avg_rating": overall["avg_rating"] if overall else None,
        "positive_pct": overall["positive_pct"] if overall else None,
        "brands": len([b for b in db[FACT].distinct("brand") if b]),
        "products": len([p for p in db[FACT].distinct("product_name") if p]),
        "datasets": db[DATASETS].count_documents({}),
        "predictions": db[PREDICTIONS].count_documents({}),
        "rating_distribution": [{"rating": r["rating"], "count": r["review_count"]} for r in by_rating],
        "monthly_trend": [{"month": r["month"], **_labels_row(r), "avg_rating": r["avg_rating"]} for r in trend],
        "top_products": [{"product": r["product"], "count": r["review_count"], "avg_rating": r["avg_rating"],
                          "positive_pct": r["positive_pct"]} for r in top_products],
        "model": model_summary,
        "recent_activity": activity[:10],
    })


@router.get("/analytics/summary", summary="Sentiment by product, brand, rating and date (filterable)")
def analytics_summary(filters: Filters = Depends(filter_params),
                      granularity: str = Query("month", pattern="^(year|quarter|month)$"),
                      top_n: int = Query(12, ge=1, le=100), db=Depends(get_db)):
    overall = cube(db, [], filters)["rows"]
    trend = cube(db, [granularity], filters)["rows"]
    return jsonable({
        "filters": filters.describe(),
        "overall": overall[0] if overall else None,
        "by_sentiment": cube(db, ["sentiment"], filters)["rows"],
        "by_rating": cube(db, ["rating"], filters)["rows"],
        "by_brand": cube(db, ["brand"], filters, sort_by="count")["rows"],
        "by_product": cube(db, ["product"], filters, sort_by="count", limit=top_n)["rows"],
        "trend": [r for r in trend if r[granularity] != "Unknown"],
        "unknown_date_reviews": sum(r["review_count"] for r in trend if r[granularity] == "Unknown"),
        "granularity": granularity,
    })
