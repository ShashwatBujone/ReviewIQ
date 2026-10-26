import math

import pandas as pd
import pytest

from services.preprocessing import (DatasetError, clean_text, normalize_label, parse_rating, rating_to_label,
                                    read_csv_bytes, suggest_mapping, validate_dataframe)


def test_clean_text_removes_noise_and_keeps_negations():
    raw = "I DON'T like it!!! See https://example.com <b>bad</b> mail me@x.com 10/10"
    out = clean_text(raw)
    assert "http" not in out and "example" not in out and "<b>" not in out and "me" not in out.split()
    assert "not" in out.split() and "like" in out.split() and "bad" in out.split()
    assert not any(ch.isdigit() for ch in out)
    assert "  " not in out


def test_clean_text_handles_missing_values():
    assert clean_text(None) == ""
    assert clean_text(float("nan")) == ""
    assert clean_text(pd.NA) == ""
    assert clean_text("   ") == ""


def test_contractions_expanded():
    assert clean_text("it won't work, can't charge") == "not work not charge"  # "will"/"can" are stop-words; "not" is kept


@pytest.mark.parametrize("rating,label", [(1, "negative"), (2, "negative"), (2.5, "neutral"), (3, "neutral"),
                                          (3.5, "neutral"), (4, "positive"), (5, "positive"), (None, None)])
def test_rating_rule(rating, label):
    assert rating_to_label(rating) == label


@pytest.mark.parametrize("raw,expected", [("5", 5.0), (" 4.0 ", 4.0), ("0", None), ("6", None), ("abc", None),
                                          ("", None), (None, None), (float("nan"), None)])
def test_parse_rating(raw, expected):
    assert parse_rating(raw) == expected


def test_normalize_label():
    assert normalize_label("Positive") == "positive"
    assert normalize_label(" NEG ") == "negative"
    assert normalize_label("meh") is None
    assert normalize_label(None) is None


def test_suggest_mapping_sample_columns(sample_df):
    m = suggest_mapping(list(sample_df.columns))
    assert m == {"review": "review", "review_title": "review_title", "rating": "rating",
                 "product_name": "product_name", "brand": "brand", "review_date": "review_date",
                 "sentiment": "sentiment"}


def test_suggest_mapping_other_schema():
    m = suggest_mapping(["reviews.text", "reviews.rating", "name", "Manufacturer", "reviews.date"])
    assert m["review"] == "reviews.text" and m["rating"] == "reviews.rating"
    assert m["product_name"] == "name" and m["brand"] == "Manufacturer" and m["review_date"] == "reviews.date"
    assert m["sentiment"] is None


def test_read_csv_errors():
    with pytest.raises(DatasetError):
        read_csv_bytes(b"")
    with pytest.raises(DatasetError):
        read_csv_bytes(b"a,b\n")
    df = read_csv_bytes("text,rating\ncaf\xe9 ok,4\n".encode("cp1252"))
    assert df.iloc[0]["text"] == "café ok"


def test_validation_detects_rating_derived_labels(sample_df):
    rep = validate_dataframe(sample_df, suggest_mapping(list(sample_df.columns)))
    assert rep["ok"]
    assert rep["row_count"] == len(sample_df)
    assert rep["label_source"] == "column"
    assert rep["label_rating_agreement"] == 1.0
    assert any("rating-derived" in w for w in rep["warnings"])
    expected = sample_df["sentiment"].value_counts()
    assert rep["label_distribution"] == {k: int(expected.get(k, 0)) for k in ["negative", "neutral", "positive"]}
    assert rep["missing_by_column"]["review_date"] == int(sample_df["review_date"].isna().sum())


def test_validation_requires_review_column():
    df = pd.DataFrame({"stars": ["5", "1"]})
    rep = validate_dataframe(df, suggest_mapping(list(df.columns)))
    assert not rep["ok"] and any("review" in e for e in rep["errors"])


def test_validation_rating_derived_and_invalid_values():
    df = pd.DataFrame({"text": ["good", "bad", "ok", "", "x"], "stars": ["5", "1", "3", "4", "9"]})
    rep = validate_dataframe(df, suggest_mapping(list(df.columns)), "rating")
    assert rep["ok"]
    assert rep["label_distribution"] == {"negative": 1, "neutral": 1, "positive": 2}
    assert rep["unlabeled_rows"] == 1
    assert any("empty review" in w for w in rep["warnings"])
    assert any("DERIVED" in w for w in rep["warnings"])
    assert not math.isnan(rep["row_count"])
