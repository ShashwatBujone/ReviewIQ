import pandas as pd

from db import DIM_BRAND, DIM_DATE, DIM_PRODUCT, DIM_SENTIMENT, ETL_RUNS, FACT
from services.etl import run_etl, transform
from services.preprocessing import suggest_mapping


def test_full_sample_load(loaded_db, sample_df):
    db = loaded_db
    assert db[FACT].count_documents({}) == len(sample_df)  # sample has no exact duplicate rows
    assert db[DIM_BRAND].count_documents({}) == sample_df["brand"].nunique()
    assert db[DIM_PRODUCT].count_documents({}) == sample_df.groupby(["brand", "product_name"]).ngroups
    assert db[DIM_SENTIMENT].count_documents({}) == 4
    dated = pd.to_datetime(sample_df["review_date"], utc=True, errors="coerce", format="mixed")
    assert db[DIM_DATE].count_documents({"_id": {"$ne": 0}}) == dated.dt.date.nunique()
    assert db[FACT].count_documents({"date_key": 0}) == int(dated.isna().sum())
    for lab, n in sample_df["sentiment"].value_counts().items():
        assert db[FACT].count_documents({"sentiment": lab}) == n
    run = db[ETL_RUNS].find_one()
    assert run["status"] == "success" and run["load"]["inserted"] == len(sample_df)


def test_reimport_skips_duplicates(loaded_db, sample_df):
    r = run_etl(loaded_db, sample_df, suggest_mapping(list(sample_df.columns)), "auto", "append", "again")
    assert r["load"]["inserted"] == 0
    assert r["load"]["duplicates_already_in_db"] == len(sample_df)
    assert loaded_db[FACT].count_documents({}) == len(sample_df)


def test_replace_mode(loaded_db):
    df = pd.DataFrame({"review": ["Great", "Awful"], "rating": ["5", "1"]})
    r = run_etl(loaded_db, df, suggest_mapping(list(df.columns)), "rating", "replace", "small")
    assert r["load"]["removed_before_load"] > 0
    assert loaded_db[FACT].count_documents({}) == 2
    assert {d["sentiment_source"] for d in loaded_db[FACT].find()} == {"rating_derived"}


def test_transform_handles_messy_rows():
    df = pd.DataFrame({
        "text": ["Nice", "Nice", "", None, "Broken", "Fine"],
        "score": ["5", "5", "4", "3", "abc", "3"],
        "date": ["2020-01-05", "2020-01-05", "x", None, "not a date", "2021-07-01T00:00:00Z"],
    })
    mapping = suggest_mapping(list(df.columns))
    assert mapping["review"] == "text" and mapping["rating"] == "score" and mapping["review_date"] == "date"
    docs, stats = transform(df, mapping, "rating", "t")
    assert stats["skipped_empty_review"] == 2
    assert stats["duplicates_in_file"] == 1
    assert stats["rows_out"] == 3 == len(docs)
    broken = next(d for d in docs if d["review"] == "Broken")
    assert broken["rating"] is None and broken["sentiment"] is None and broken["date_key"] == 0
    fine = next(d for d in docs if d["review"] == "Fine")
    assert fine["quarter_label"] == "2021-Q3" and fine["year_month"] == "2021-07" and fine["sentiment"] == "neutral"
    assert stats["labels"] == {"negative": 0, "neutral": 1, "positive": 1} and stats["unlabeled"] == 1
    assert {d["product_name"] for d in docs} == {"Unknown product"}
