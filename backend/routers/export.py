"""CSV exports."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from db import FACT, PREDICTIONS, get_db
from deps import filter_params, model_service
from services.olap import Filters, build_match

router = APIRouter(prefix="/api/export", tags=["Export"])

REVIEW_COLUMNS = ["_id", "product_name", "brand", "review_date", "review_title", "review", "cleaned_review",
                  "rating", "sentiment", "sentiment_source", "year", "quarter_label", "year_month",
                  "review_length", "dataset_id"]


def _csv_response(rows, columns: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    # UTF-8 BOM so Excel on Windows opens accented characters correctly
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/reviews", summary="Export (filtered) reviews as CSV")
def export_reviews(filters: Filters = Depends(filter_params), db=Depends(get_db)):
    rows = db[FACT].find(build_match(filters)).sort("review_date", -1)
    return _csv_response(rows, REVIEW_COLUMNS, "reviewiq_reviews.csv")


@router.get("/predictions", summary="Export prediction history as CSV")
def export_predictions(db=Depends(get_db)):
    rows = []
    for d in db[PREDICTIONS].find().sort("created_at", -1):
        row = {"id": d["_id"], "created_at": d["created_at"].isoformat() if hasattr(d["created_at"], "isoformat") else d["created_at"],
               "text": d["text"], "model_run": d.get("model_run")}
        for name, p in d["predictions"].items():
            row[f"{name}_label"] = p["label"]
            row[f"{name}_confidence"] = p["confidence"]
        rows.append(row)
    cols = ["id", "created_at", "text", "model_run", "logistic_regression_label", "logistic_regression_confidence",
            "naive_bayes_label", "naive_bayes_confidence"]
    return _csv_response(rows, cols, "reviewiq_predictions.csv")


@router.get("/model-metrics", summary="Export the current models' evaluation metrics as CSV")
def export_metrics():
    meta = model_service.metadata
    if not meta:
        raise HTTPException(404, "Models have not been trained yet.")
    rows = []
    for key, r in meta["results"].items():
        rows.append({"model": r["name"], "class": "ALL (macro)", "accuracy": r["accuracy"],
                     "precision": r["precision_macro"], "recall": r["recall_macro"], "f1": r["f1_macro"],
                     "support": meta["data"]["test_size"]})
        for lab, m in r["per_class"].items():
            rows.append({"model": r["name"], "class": lab, "accuracy": "", "precision": m["precision"],
                         "recall": m["recall"], "f1": m["f1"], "support": m["support"]})
    return _csv_response(rows, ["model", "class", "accuracy", "precision", "recall", "f1", "support"],
                         "reviewiq_model_metrics.csv")
