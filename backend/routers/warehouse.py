"""Data warehouse: star schema description, ETL history and OLAP operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from db import (DATASETS, DIM_BRAND, DIM_DATE, DIM_PRODUCT, DIM_SENTIMENT, ETL_RUNS, FACT, MODEL_RUNS,
                PREDICTIONS, get_db, state)
from deps import filter_params, jsonable
from schemas import CubeRequest, DiceRequest, SliceRequest
from services.etl import rebuild_dimensions
from services.olap import DIMENSIONS, HIERARCHIES, Filters, cube, dice_cube, drill_down, roll_up, slice_cube

router = APIRouter(prefix="/api/warehouse", tags=["Data Warehouse & OLAP"])

SCHEMA = {
    "note": ("This is a LOGICAL star schema. MongoDB is a document database, not a relational one: the fact and "
             "dimension tables are MongoDB collections, the keys are stored as fields, and analytical queries run "
             "as MongoDB aggregation pipelines. Dimension attributes are also denormalised onto each fact document "
             "so most OLAP queries need no $lookup (joins)."),
    "fact": {"collection": FACT, "grain": "one customer review",
             "keys": ["product_key → dim_product", "brand_key → dim_brand", "date_key → dim_date",
                      "sentiment_key → dim_sentiment"],
             "measures": ["review count (COUNT)", "rating (AVG)", "review_length in words (AVG)",
                          "positive / neutral / negative counts (SUM)"]},
    "dimensions": [
        {"collection": DIM_PRODUCT, "key": "product_key", "attributes": ["product_name", "brand", "brand_key"],
         "hierarchy": "brand → product"},
        {"collection": DIM_BRAND, "key": "brand_key", "attributes": ["brand"], "hierarchy": "all → brand"},
        {"collection": DIM_DATE, "key": "date_key (YYYYMMDD, 0 = unknown)",
         "attributes": ["date", "year", "quarter", "month", "month_name", "day", "weekday"],
         "hierarchy": "year → quarter → month → day"},
        {"collection": DIM_SENTIMENT, "key": "sentiment_key", "attributes": ["label", "rating_rule"],
         "hierarchy": "sentiment → rating"},
    ],
}


def _filters_from(body_filters: dict) -> Filters:
    try:
        return Filters.from_dict(body_filters)
    except TypeError as exc:
        raise HTTPException(422, f"Invalid filters: {exc}")


@router.get("/schema", summary="Star schema description with live collection counts and sample documents")
def schema(db=Depends(get_db)):
    counts = {c: db[c].count_documents({}) for c in
              [FACT, DIM_PRODUCT, DIM_BRAND, DIM_DATE, DIM_SENTIMENT, DATASETS, ETL_RUNS, MODEL_RUNS, PREDICTIONS]}
    samples = {}
    for c in [FACT, DIM_PRODUCT, DIM_BRAND, DIM_DATE, DIM_SENTIMENT]:
        doc = db[c].find_one({"date_key": {"$ne": 0}} if c == FACT else ({"_id": {"$ne": 0}} if c == DIM_DATE else {}))
        if doc and c == FACT:
            doc["review"] = doc["review"][:160] + ("…" if len(doc["review"]) > 160 else "")
            doc["cleaned_review"] = doc["cleaned_review"][:120] + "…"
        samples[c] = doc
    return jsonable({**SCHEMA, "counts": counts, "samples": samples, "storage": state.info(),
                     "olap_dimensions": list(DIMENSIONS), "hierarchies": HIERARCHIES})


@router.get("/etl-runs", summary="ETL run history")
def etl_runs(limit: int = 20, db=Depends(get_db)):
    return jsonable(list(db[ETL_RUNS].find({}, {"mapping": 0}).sort("started_at", -1).limit(limit)))


@router.post("/rebuild-dimensions", summary="Rebuild dimension collections from the fact collection")
def rebuild(db=Depends(get_db)):
    return rebuild_dimensions(db)


@router.post("/reset", summary="Delete all warehouse data (facts, dimensions, datasets, ETL runs)")
def reset(confirm: bool = Query(False, description="Must be true"), db=Depends(get_db)):
    if not confirm:
        raise HTTPException(400, "Pass confirm=true to delete all warehouse data.")
    deleted = {c: db[c].delete_many({}).deleted_count
               for c in [FACT, DIM_PRODUCT, DIM_BRAND, DIM_DATE, DIM_SENTIMENT, DATASETS, ETL_RUNS]}
    return {"deleted": deleted, "note": "Trained models and prediction history were kept."}


# ----------------------------------------------------------------------------- OLAP
def _run(fn, *args, **kwargs):
    try:
        return jsonable(fn(*args, **kwargs))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/cube", summary="Generic cube query: group by any dimensions with filters")
def cube_query(req: CubeRequest, db=Depends(get_db)):
    return _run(cube, db, req.group_by, _filters_from(req.filters), req.sort_by, req.limit)


@router.get("/olap/rollup", summary="Roll-up along a hierarchy (e.g. month → quarter → year → all)")
def olap_rollup(hierarchy: str = Query("date", description="date | product | sentiment"),
                level: str = Query("year", description="Target level, or 'all' for the grand total"),
                filters: Filters = Depends(filter_params), db=Depends(get_db)):
    return _run(roll_up, db, hierarchy, level, filters)


@router.get("/olap/drilldown", summary="Drill-down to the next finer level (optionally inside one member)")
def olap_drilldown(hierarchy: str = Query("date"), level: str = Query("year", description="Level to drill FROM"),
                   member: str | None = Query(None, description="e.g. 2017 when drilling from year"),
                   filters: Filters = Depends(filter_params), db=Depends(get_db)):
    return _run(drill_down, db, hierarchy, level, member, filters)


@router.post("/olap/slice", summary="Slice: fix one dimension to a single value")
def olap_slice(req: SliceRequest, db=Depends(get_db)):
    return _run(slice_cube, db, req.dimension, req.value, req.group_by, _filters_from(req.filters))


@router.post("/olap/dice", summary="Dice: select value sets on two or more dimensions")
def olap_dice(req: DiceRequest, db=Depends(get_db)):
    return _run(dice_cube, db, req.selections, req.group_by, _filters_from(req.filters))
