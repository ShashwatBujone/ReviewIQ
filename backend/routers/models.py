"""Model training, evaluation results and status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from db import FACT, MODEL_RUNS, get_db
from deps import jsonable, model_service
from schemas import TrainRequest
from services.etl import now_utc
from services.ml import TrainingError
from services.preprocessing import LABELS, model_input_text, rating_rule

router = APIRouter(prefix="/api/models", tags=["Models"])


def train_from_db(db, req: TrainRequest) -> dict:
    query: dict = {"sentiment": {"$in": LABELS}}
    if req.dataset_id:
        query["dataset_id"] = req.dataset_id
    texts, labels, sources = [], [], {}
    for d in db[FACT].find(query, {"review": 1, "review_title": 1, "sentiment": 1, "sentiment_source": 1}):
        texts.append(model_input_text(d.get("review_title"), d.get("review"), req.include_title))
        labels.append(d["sentiment"])
        src = d.get("sentiment_source") or "unknown"
        sources[src] = sources.get(src, 0) + 1
    total = db[FACT].count_documents({"dataset_id": req.dataset_id} if req.dataset_id else {})
    if not texts:
        raise TrainingError("No labeled reviews are available. Import a dataset with a sentiment column or a rating column first.")
    summary = {"reviews_in_scope": total, "labeled_reviews": len(texts), "excluded_unlabeled": total - len(texts),
               "label_sources": sources, "rating_rule": rating_rule(), "dataset_id": req.dataset_id}
    meta = model_service.train(texts, labels, req.model_dump(), summary)
    db[MODEL_RUNS].insert_one({"_id": meta["run_id"], **meta, "trained_at": now_utc()})
    return meta


@router.post("/train", summary="Train Logistic Regression and Multinomial Naive Bayes on labeled reviews")
def train(req: TrainRequest, db=Depends(get_db)):
    try:
        return jsonable(train_from_db(db, req))
    except TrainingError as exc:
        raise HTTPException(422, str(exc))


@router.get("/status", summary="Whether trained models are loaded")
def status():
    return model_service.status()


@router.get("/evaluation", summary="Evaluation results of the currently loaded models")
def evaluation():
    if not model_service.metadata:
        raise HTTPException(404, model_service.load_error or "Models have not been trained yet.")
    return model_service.metadata


@router.get("/runs", summary="History of training runs (stored in MongoDB)")
def runs(limit: int = 20, db=Depends(get_db)):
    docs = db[MODEL_RUNS].find({}, {"results.logistic_regression.top_features": 0,
                                    "results.naive_bayes.top_features": 0}).sort("trained_at", -1).limit(limit)
    return jsonable(list(docs))
