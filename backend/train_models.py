"""Command-line training: python train_models.py [path/to/reviews.csv]

Runs the same ETL + training code as the API, using a temporary in-memory store, and saves
the vectoriser, both models and model_metadata.json to backend/models/. Handy for (re)creating
the saved models without starting the server or MongoDB.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import mongomock

from config import settings
from db import ensure_indexes
from deps import model_service
from routers.models import train_from_db
from schemas import TrainRequest
from services.etl import run_etl
from services.preprocessing import read_csv_path, suggest_mapping


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.sample_data_path
    df = read_csv_path(path)
    db = mongomock.MongoClient()["reviewiq_cli"]
    ensure_indexes(db)
    etl = run_etl(db, df, suggest_mapping(list(df.columns)), "auto", "append", "cli", path.name)
    print(f"ETL: {etl['load']['inserted']} reviews loaded from {path}")
    meta = train_from_db(db, TrainRequest())
    print(f"Saved models to {model_service.model_dir}")
    print(f"Majority baseline: accuracy {meta['baseline']['accuracy']:.3f}, macro F1 {meta['baseline']['f1_macro']:.3f}")
    for key, r in meta["results"].items():
        print(f"{r['name']:<26} acc {r['accuracy']:.3f}  macro-P {r['precision_macro']:.3f}  "
              f"macro-R {r['recall_macro']:.3f}  macro-F1 {r['f1_macro']:.3f}  CV-F1 {r.get('cv_f1_macro_mean', float('nan')):.3f}")
    print("Selected model:", meta["results"][meta["best_model"]]["name"], f"(by {meta['selection_metric']})")
    print(json.dumps(meta["data"]["class_distribution"]))


if __name__ == "__main__":
    main()
