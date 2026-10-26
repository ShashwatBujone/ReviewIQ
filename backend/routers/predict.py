"""Sentiment prediction (single text and batch CSV) plus prediction history."""
from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from config import settings
from db import PREDICTIONS, get_db, state
from deps import jsonable, model_service
from schemas import PredictRequest
from services.etl import now_utc
from services.ml import MODEL_NAMES, TrainingError
from services.preprocessing import DatasetError, read_csv_bytes, suggest_mapping

router = APIRouter(prefix="/api/predict", tags=["Prediction"])


@router.post("", summary="Predict the sentiment of a review")
def predict(req: PredictRequest):
    try:
        result = model_service.predict(req.text, req.model)
    except TrainingError as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result["saved"] = False
    if req.save and settings.save_predictions and state.db is not None:
        doc = {"_id": uuid.uuid4().hex[:12], "text": req.text[:2000], "created_at": now_utc(),
               "model_run": model_service.metadata.get("run_id") if model_service.metadata else None,
               "predictions": {k: {"label": v["label"], "confidence": v["confidence"]}
                               for k, v in result["predictions"].items()}}
        state.db[PREDICTIONS].insert_one(doc)
        result["saved"] = True
        result["id"] = doc["_id"]
    return result


@router.post("/batch", summary="Upload a CSV and download it with predicted sentiment columns")
async def predict_batch(file: UploadFile = File(...), text_column: str | None = Form(None),
                        model: str = Form("logistic_regression")):
    if model not in MODEL_NAMES:
        raise HTTPException(422, f"model must be one of {', '.join(MODEL_NAMES)}")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than the {settings.max_upload_mb} MB limit.")
    try:
        df = read_csv_bytes(data)
    except DatasetError as exc:
        raise HTTPException(422, str(exc))
    col = text_column or suggest_mapping(list(df.columns)).get("review")
    if not col or col not in df.columns:
        raise HTTPException(422, "Could not find the review text column; pass text_column explicitly. "
                                 f"Columns: {', '.join(df.columns)}")
    try:
        preds = model_service.predict_many(df[col].fillna("").astype(str).tolist(), model)
    except TrainingError as exc:
        raise HTTPException(409, str(exc))
    df["predicted_sentiment"] = [p["label"] for p in preds]
    df["prediction_confidence"] = [p["confidence"] for p in preds]
    df["prediction_model"] = MODEL_NAMES[model]
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="predictions.csv"'})


@router.get("/history", summary="Recent saved predictions")
def history(limit: int = 20, db=Depends(get_db)):
    return jsonable(list(db[PREDICTIONS].find().sort("created_at", -1).limit(min(limit, 200))))


@router.delete("/history", summary="Clear prediction history")
def clear_history(db=Depends(get_db)):
    return {"deleted": db[PREDICTIONS].delete_many({}).deleted_count}

