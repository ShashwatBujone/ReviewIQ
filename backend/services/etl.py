"""ETL: Extract (CSV) -> Transform (clean, validate, derive keys/labels) -> Load (MongoDB star schema).

Logical star schema implemented with MongoDB collections:
  fact_reviews   one document per review (measures: rating, review_length, sentiment counts)
                 holding foreign keys product_key, brand_key, date_key, sentiment_key.
                 Dimension attributes (brand, product_name, year, ...) are also denormalised
                 onto the fact so aggregation pipelines don't need $lookup for every query.
  dim_product    product_key -> product_name, brand
  dim_brand      brand_key -> brand
  dim_date       date_key (YYYYMMDD, 0 = unknown) -> date, year, quarter, month, ...
  dim_sentiment  sentiment_key -> label, rule
"""
from __future__ import annotations

import calendar
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from db import DATASETS, DIM_BRAND, DIM_DATE, DIM_PRODUCT, DIM_SENTIMENT, ETL_RUNS, FACT
from services.preprocessing import (
    LABELS, DatasetError, clean_text, is_missing, fact_key, normalize_label, parse_dates, parse_rating,
    rating_rule, rating_to_label, resolve_label_source, validate_dataframe,
)

UNKNOWN_PRODUCT = "Unknown product"
UNKNOWN_BRAND = "Unknown brand"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _key(prefix: str, *parts: str, n: int = 10) -> str:
    return prefix + hashlib.sha1("|".join(p.lower() for p in parts).encode()).hexdigest()[:n]


def _text(v: Any) -> str:
    if is_missing(v):
        return ""
    return str(v).strip()


def transform(df: pd.DataFrame, mapping: dict, label_source: str, dataset_id: str) -> tuple[list[dict], dict]:
    """Turn raw rows into fact documents. Returns (docs, stats)."""
    source = resolve_label_source(mapping, label_source)
    col = lambda f: df[mapping[f]] if mapping.get(f) else pd.Series([None] * len(df), index=df.index)  # noqa: E731

    dates = parse_dates(col("review_date")) if mapping.get("review_date") else pd.Series([pd.NaT] * len(df), index=df.index)
    stats = {"rows_in": int(len(df)), "skipped_empty_review": 0, "duplicates_in_file": 0,
             "missing_dates": 0, "invalid_or_missing_ratings": 0, "unlabeled": 0,
             "label_source": source, "labels": {k: 0 for k in LABELS}}
    docs: dict[str, dict] = {}

    for idx, (review, title, rating_raw, product, brand, label_raw, dt) in enumerate(zip(
            col("review"), col("review_title"), col("rating"), col("product_name"),
            col("brand"), col("sentiment"), dates)):
        review_s = _text(review)
        if not review_s:
            stats["skipped_empty_review"] += 1
            continue
        title_s = _text(title)
        product_s = _text(product) or UNKNOWN_PRODUCT
        brand_s = _text(brand) or UNKNOWN_BRAND
        rating = parse_rating(rating_raw) if mapping.get("rating") else None
        if rating is None:
            stats["invalid_or_missing_ratings"] += 1

        if source == "column":
            label = normalize_label(label_raw)
        elif source == "rating":
            label = rating_to_label(rating)
        else:
            label = None
        if label is None:
            stats["unlabeled"] += 1
        else:
            stats["labels"][label] += 1

        if pd.isna(dt):
            stats["missing_dates"] += 1
            date_str, date_key, year, quarter, q_label, month, ym = None, 0, None, None, None, None, None
        else:
            date_str = dt.date().isoformat()
            date_key = int(dt.strftime("%Y%m%d"))
            year, month = dt.year, dt.month
            quarter = (month - 1) // 3 + 1
            q_label, ym = f"{year}-Q{quarter}", f"{year}-{month:02d}"

        key = fact_key(product_s, brand_s, title_s, review_s, date_str, rating)
        if key in docs:
            stats["duplicates_in_file"] += 1
            if label is None:
                stats["unlabeled"] -= 1
            else:
                stats["labels"][label] -= 1
            continue
        docs[key] = {
            "_id": key,
            # foreign keys to the dimensions
            "product_key": _key("P", brand_s, product_s),
            "brand_key": _key("B", brand_s, n=8),
            "date_key": date_key,
            "sentiment_key": label or "unlabeled",
            # denormalised dimension attributes
            "product_name": product_s,
            "brand": brand_s,
            "review_date": date_str,
            "year": year,
            "quarter": quarter,
            "quarter_label": q_label,
            "month": month,
            "year_month": ym,
            # descriptive attributes
            "review_title": title_s,
            "review": review_s,
            "cleaned_review": clean_text(review_s),
            # measures
            "rating": rating,
            "sentiment": label,
            "sentiment_source": None if label is None else ("rating_derived" if source == "rating" else "dataset_column"),
            "review_length": len(review_s.split()),
            # lineage
            "dataset_id": dataset_id,
            "source_row": idx,
        }
    stats["rows_out"] = len(docs)
    return list(docs.values()), stats


def load(db, docs: list[dict], mode: str = "append") -> dict:
    fact = db[FACT]
    removed = 0
    if mode == "replace":
        removed = fact.delete_many({}).deleted_count
    inserted = existing = 0
    batch = 1000
    for i in range(0, len(docs), batch):
        chunk = docs[i:i + batch]
        ids = [d["_id"] for d in chunk]
        present = {d["_id"] for d in fact.find({"_id": {"$in": ids}}, {"_id": 1})}
        new = [d for d in chunk if d["_id"] not in present]
        existing += len(present)
        if new:
            fact.insert_many(new, ordered=False)
            inserted += len(new)
    return {"inserted": inserted, "duplicates_already_in_db": existing, "removed_before_load": removed}


def rebuild_dimensions(db) -> dict:
    """(Re)build the dimension collections from the fact collection."""
    fact = db[FACT]
    products, brands, dates = {}, {}, {}
    for d in fact.find({}, {"product_key": 1, "product_name": 1, "brand": 1, "brand_key": 1,
                            "date_key": 1, "review_date": 1, "year": 1, "quarter": 1, "month": 1}):
        products[d["product_key"]] = {"_id": d["product_key"], "product_name": d["product_name"],
                                      "brand": d["brand"], "brand_key": d["brand_key"]}
        brands[d["brand_key"]] = {"_id": d["brand_key"], "brand": d["brand"]}
        if d["date_key"] not in dates:
            if d["date_key"] == 0:
                dates[0] = {"_id": 0, "date": None, "year": None, "quarter": None, "month": None,
                            "month_name": None, "day": None, "weekday": None, "label": "Unknown date"}
            else:
                dt = datetime.strptime(d["review_date"], "%Y-%m-%d")
                dates[d["date_key"]] = {"_id": d["date_key"], "date": d["review_date"], "year": dt.year,
                                        "quarter": (dt.month - 1) // 3 + 1, "month": dt.month,
                                        "month_name": calendar.month_name[dt.month], "day": dt.day,
                                        "weekday": calendar.day_name[dt.weekday()], "label": d["review_date"]}
    rule = rating_rule()
    sentiments = [{"_id": k, "label": k.capitalize(), "rating_rule": rule[k]} for k in LABELS]
    sentiments.append({"_id": "unlabeled", "label": "Unlabeled", "rating_rule": "no valid label"})
    for name, rows in [(DIM_PRODUCT, products.values()), (DIM_BRAND, brands.values()),
                       (DIM_DATE, dates.values()), (DIM_SENTIMENT, sentiments)]:
        db[name].delete_many({})
        rows = list(rows)
        if rows:
            db[name].insert_many(rows)
    return {"dim_product": len(products), "dim_brand": len(brands), "dim_date": len(dates),
            "dim_sentiment": len(sentiments)}


def run_etl(db, df: pd.DataFrame, mapping: dict, label_source: str = "auto", mode: str = "append",
            dataset_id: str | None = None, source_name: str = "upload") -> dict:
    """Full ETL with a recorded run document. Raises DatasetError on invalid input."""
    validation = validate_dataframe(df, mapping, label_source)
    if not validation["ok"]:
        raise DatasetError("; ".join(validation["errors"]))
    if mode not in {"append", "replace"}:
        raise DatasetError("mode must be 'append' or 'replace'")

    run_id = uuid.uuid4().hex[:12]
    started = now_utc()
    run = {"_id": run_id, "dataset_id": dataset_id, "source": source_name, "started_at": started,
           "status": "running", "mapping": mapping, "mode": mode}
    db[ETL_RUNS].insert_one(run)
    try:
        docs, tstats = transform(df, mapping, label_source, dataset_id or run_id)
        lstats = load(db, docs, mode)
        dims = rebuild_dimensions(db)
        finished = now_utc()
        result = {
            "status": "success",
            "finished_at": finished,
            "duration_ms": int((finished - started).total_seconds() * 1000),
            "extract": {"rows_read": int(len(df)), "columns": list(df.columns)},
            "transform": tstats,
            "load": lstats,
            "dimensions": dims,
            "warnings": validation["warnings"],
        }
        db[ETL_RUNS].update_one({"_id": run_id}, {"$set": result})
        if dataset_id:
            db[DATASETS].update_one({"_id": dataset_id}, {"$set": {
                "status": "imported", "imported_at": finished, "last_etl_run": run_id,
                "mapping": mapping, "label_source": tstats["label_source"]}})
        return {"run_id": run_id, **result}
    except Exception as exc:
        db[ETL_RUNS].update_one({"_id": run_id}, {"$set": {"status": "failed", "error": str(exc),
                                                           "finished_at": now_utc()}})
        raise
