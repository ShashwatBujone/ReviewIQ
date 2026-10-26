"""Dataset upload, validation, column mapping and ETL import."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import settings
from db import DATASETS, FACT, get_db
from deps import jsonable
from schemas import ImportRequest, ValidateRequest
from services.etl import now_utc, rebuild_dimensions, run_etl
from services.preprocessing import (FIELDS, DatasetError, preview_rows, rating_rule, read_csv_bytes,
                                    read_csv_path, suggest_mapping, validate_dataframe)

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

SAMPLE_ID = "sample"


def _dataset_path(dataset_id: str) -> Path:
    return settings.upload_dir / f"{dataset_id}.csv"


def _load_dataset_df(db, dataset_id: str):
    meta = db[DATASETS].find_one({"_id": dataset_id})
    if not meta:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.")
    path = Path(meta["stored_path"])
    if not path.exists():
        raise HTTPException(410, f"The stored file for dataset '{dataset_id}' no longer exists on disk.")
    return meta, read_csv_path(path)


def register_dataframe(db, df, filename: str, stored_path: Path, dataset_id: str) -> dict:
    mapping = suggest_mapping(list(df.columns))
    validation = validate_dataframe(df, mapping, "auto")
    doc = {"_id": dataset_id, "filename": filename, "stored_path": str(stored_path), "uploaded_at": now_utc(),
           "row_count": int(len(df)), "columns": list(df.columns), "suggested_mapping": mapping,
           "validation": validation, "status": "uploaded"}
    db[DATASETS].replace_one({"_id": dataset_id}, doc, upsert=True)
    return {**doc, "preview": preview_rows(df), "fields": FIELDS, "rating_rule": rating_rule()}


@router.post("/upload", status_code=201, summary="Upload a CSV, validate it and suggest a column mapping")
async def upload_dataset(file: UploadFile = File(...), db=Depends(get_db)):
    name = file.filename or "upload.csv"
    if not name.lower().endswith(".csv"):
        raise HTTPException(415, "Only .csv files are supported.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than the {settings.max_upload_mb} MB limit.")
    try:
        df = read_csv_bytes(data)
    except DatasetError as exc:
        raise HTTPException(422, str(exc))
    dataset_id = uuid.uuid4().hex[:12]
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = _dataset_path(dataset_id)
    path.write_bytes(data)
    return jsonable(register_dataframe(db, df, name, path, dataset_id))


@router.get("", summary="List uploaded datasets")
def list_datasets(db=Depends(get_db)):
    docs = list(db[DATASETS].find({}, {"validation.missing_by_column": 0}).sort("uploaded_at", -1))
    for d in docs:
        d["reviews_in_warehouse"] = db[FACT].count_documents({"dataset_id": d["_id"]})
    return jsonable(docs)


@router.get("/sample/download", summary="Download the bundled sample CSV")
def download_sample():
    if not settings.sample_data_path.exists():
        raise HTTPException(404, "Sample dataset file is missing.")
    return FileResponse(settings.sample_data_path, media_type="text/csv",
                        filename=settings.sample_data_path.name)


@router.post("/sample/import", summary="Register and import the bundled sample dataset")
def import_sample(mode: str = "append", db=Depends(get_db)):
    return jsonable(import_sample_dataset(db, mode))


def import_sample_dataset(db, mode: str = "append") -> dict:
    path = settings.sample_data_path
    if not path.exists():
        raise HTTPException(404, f"Sample dataset not found at {path}.")
    df = read_csv_path(path)
    info = register_dataframe(db, df, path.name, path, SAMPLE_ID)
    try:
        etl = run_etl(db, df, info["suggested_mapping"], "auto", mode, SAMPLE_ID, "sample")
    except DatasetError as exc:
        raise HTTPException(422, str(exc))
    return {"dataset": {k: v for k, v in info.items() if k != "preview"}, "etl": etl}


@router.get("/{dataset_id}", summary="Dataset details with preview")
def get_dataset(dataset_id: str, db=Depends(get_db)):
    meta, df = _load_dataset_df(db, dataset_id)
    meta["preview"] = preview_rows(df)
    meta["fields"] = FIELDS
    meta["rating_rule"] = rating_rule()
    meta["reviews_in_warehouse"] = db[FACT].count_documents({"dataset_id": dataset_id})
    return jsonable(meta)


@router.post("/{dataset_id}/validate", summary="Validate the dataset with a custom column mapping")
def validate_dataset(dataset_id: str, req: ValidateRequest, db=Depends(get_db)):
    _, df = _load_dataset_df(db, dataset_id)
    return validate_dataframe(df, req.mapping.model_dump(), req.label_source)


@router.post("/{dataset_id}/import", summary="Run ETL: transform the CSV and load it into the warehouse")
def import_dataset(dataset_id: str, req: ImportRequest, db=Depends(get_db)):
    meta, df = _load_dataset_df(db, dataset_id)
    mapping = req.mapping.model_dump() if req.mapping else meta["suggested_mapping"]
    try:
        return jsonable(run_etl(db, df, mapping, req.label_source, req.mode, dataset_id, meta["filename"]))
    except DatasetError as exc:
        raise HTTPException(422, str(exc))


@router.delete("/{dataset_id}", summary="Delete a dataset and the reviews it loaded")
def delete_dataset(dataset_id: str, db=Depends(get_db)):
    meta = db[DATASETS].find_one({"_id": dataset_id})
    if not meta:
        raise HTTPException(404, f"Dataset '{dataset_id}' not found.")
    removed = db[FACT].delete_many({"dataset_id": dataset_id}).deleted_count
    db[DATASETS].delete_one({"_id": dataset_id})
    path = Path(meta["stored_path"])
    if dataset_id != SAMPLE_ID and path.exists() and path.parent == settings.upload_dir:
        path.unlink()
    rebuild_dimensions(db)
    return {"deleted": dataset_id, "reviews_removed": removed}
