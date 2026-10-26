"""Test configuration: run against the in-memory store with an isolated model directory."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Must be set before any backend module is imported.
os.environ["FORCE_MEMORY_STORE"] = "true"
os.environ["AUTO_IMPORT_SAMPLE"] = "true"
os.environ["MODEL_DIR"] = tempfile.mkdtemp(prefix="reviewiq_models_")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="reviewiq_uploads_")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

SAMPLE = ROOT / "data" / "sample" / "customer_reviews_preprocessed.csv"


@pytest.fixture(scope="session")
def sample_df():
    return pd.read_csv(SAMPLE, dtype=str)


@pytest.fixture()
def db():
    import mongomock
    from db import ensure_indexes
    d = mongomock.MongoClient()["reviewiq_test"]
    ensure_indexes(d)
    return d


@pytest.fixture()
def loaded_db(db, sample_df):
    from services.etl import run_etl
    from services.preprocessing import suggest_mapping
    run_etl(db, sample_df, suggest_mapping(list(sample_df.columns)), "auto", "append", "sample", "sample")
    return db


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        yield c
