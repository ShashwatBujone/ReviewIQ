"""Text cleaning, column mapping and dataset validation.

The SAME clean_text() function is used for training and for inference so the model
always sees text processed identically.
"""
from __future__ import annotations

import hashlib
import io
import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from config import settings

LABELS = ["negative", "neutral", "positive"]

# ----------------------------------------------------------------------------- text cleaning
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_NON_ALPHA_RE = re.compile(r"[^a-z\s]")
_WS_RE = re.compile(r"\s+")

_CONTRACTIONS = [
    (re.compile(r"\bwon't\b"), "will not"),
    (re.compile(r"\bcan't\b"), "can not"),
    (re.compile(r"\bain't\b"), "is not"),
    (re.compile(r"n't\b"), " not"),
    (re.compile(r"'re\b"), " are"),
    (re.compile(r"'ll\b"), " will"),
    (re.compile(r"'ve\b"), " have"),
    (re.compile(r"'m\b"), " am"),
    (re.compile(r"'d\b"), " would"),
    (re.compile(r"'s\b"), ""),
]

# Negations and intensity words carry sentiment, so they are NOT removed as stopwords.
_KEEP = {"no", "not", "nor", "never", "none", "nothing", "neither", "nobody", "nowhere",
         "cannot", "without", "but", "against", "too", "very", "few", "less", "least",
         "more", "most", "only", "off", "down", "up"}
STOPWORDS = frozenset(ENGLISH_STOP_WORDS) - _KEEP


def is_missing(value: Any) -> bool:
    """True for None / NaN / pd.NA / NaT (scalar values only)."""
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def clean_text(text: Any, remove_stopwords: bool = True) -> str:
    """Normalise raw review text: lowercase, expand contractions, strip URLs/HTML/emails,
    punctuation, digits and extra whitespace, then drop non-sentiment stopwords."""
    if is_missing(text):
        return ""
    s = str(text).lower().replace("’", "'").replace("`", "'")
    s = _HTML_RE.sub(" ", s)
    s = _URL_RE.sub(" ", s)
    s = _EMAIL_RE.sub(" ", s)
    for pattern, repl in _CONTRACTIONS:
        s = pattern.sub(repl, s)
    s = _NON_ALPHA_RE.sub(" ", s)
    tokens = [t for t in _WS_RE.split(s) if len(t) > 1 or t in {"a", "i"}]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return " ".join(tokens).strip()


def model_input_text(title: Any, review: Any, include_title: bool = True) -> str:
    """Builds the text the models are trained on / predict from."""
    parts = []
    if include_title and isinstance(title, str) and title.strip():
        parts.append(title)
    if not is_missing(review):
        parts.append(str(review))
    return clean_text(" . ".join(parts))


# ----------------------------------------------------------------------------- labels
_LABEL_ALIASES = {
    "positive": "positive", "pos": "positive", "good": "positive",
    "neutral": "neutral", "neu": "neutral", "mixed": "neutral",
    "negative": "negative", "neg": "negative", "bad": "negative",
}


def normalize_label(value: Any) -> str | None:
    if is_missing(value):
        return None
    return _LABEL_ALIASES.get(str(value).strip().lower())


def parse_rating(value: Any) -> float | None:
    """Returns a rating within [RATING_MIN, RATING_MAX] or None if missing/invalid."""
    if is_missing(value):
        return None
    try:
        r = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if np.isnan(r) or r < settings.rating_min or r > settings.rating_max:
        return None
    return r


def rating_to_label(rating: float | None) -> str | None:
    """Rating-derived label (NOT an independently verified sentiment annotation)."""
    if is_missing(rating):  # also catches NaN produced by pandas .map()
        return None
    if rating <= settings.rating_negative_max:
        return "negative"
    if rating >= settings.rating_positive_min:
        return "positive"
    return "neutral"


def rating_rule() -> dict:
    return {
        "negative": f"rating <= {settings.rating_negative_max:g}",
        "neutral": f"{settings.rating_negative_max:g} < rating < {settings.rating_positive_min:g}",
        "positive": f"rating >= {settings.rating_positive_min:g}",
        "valid_range": f"{settings.rating_min:g}-{settings.rating_max:g}",
        "note": "Rating-derived labels are a proxy for sentiment, not independently verified annotations.",
    }


# ----------------------------------------------------------------------------- column mapping
FIELDS = ["review", "review_title", "rating", "product_name", "brand", "review_date", "sentiment"]
REQUIRED_FIELDS = ["review"]
FIELD_SYNONYMS: dict[str, list[str]] = {
    "review": ["review", "review_text", "reviews_text", "text", "review_body", "body", "content",
               "comment", "comments", "reviewtext", "review_content"],
    "review_title": ["review_title", "reviews_title", "title", "summary", "headline", "review_summary"],
    "rating": ["rating", "ratings", "reviews_rating", "stars", "star_rating", "score", "overall"],
    "product_name": ["product_name", "product", "name", "product_title", "item", "item_name", "asin"],
    "brand": ["brand", "brand_name", "manufacturer", "maker", "company", "vendor"],
    "review_date": ["review_date", "reviews_date", "date", "reviewdate", "review_time", "created_at",
                    "timestamp", "date_added", "posted", "posted_date", "post_date", "review_posted"],
    "sentiment": ["sentiment", "sentiment_label", "label", "polarity", "class"],
}


def _norm_col(col: str) -> str:
    return re.sub(r"[\s.\-]+", "_", str(col).strip().lower())


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    """Guess which CSV column feeds each logical field using a synonym list."""
    normalized = {_norm_col(c): c for c in columns}
    used: set[str] = set()
    mapping: dict[str, str | None] = {}
    for field in FIELDS:
        mapping[field] = None
        for syn in FIELD_SYNONYMS[field]:
            col = normalized.get(syn)
            if col is not None and col not in used:
                mapping[field] = col
                used.add(col)
                break
    return mapping


# ----------------------------------------------------------------------------- CSV reading
class DatasetError(ValueError):
    """Raised for user-facing dataset problems (returned as HTTP 400/422)."""


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    if not data or not data.strip():
        raise DatasetError("The uploaded file is empty.")
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(data), dtype=str, encoding=enc, keep_default_na=True,
                             skipinitialspace=True, on_bad_lines="warn")
            break
        except UnicodeDecodeError as exc:
            last_err = exc
        except pd.errors.EmptyDataError:
            raise DatasetError("The CSV file has no columns or rows.")
        except pd.errors.ParserError as exc:
            raise DatasetError(f"The file could not be parsed as CSV: {exc}")
    else:
        raise DatasetError(f"Could not decode the file: {last_err}")
    df.columns = [str(c).strip() for c in df.columns]
    if df.columns.duplicated().any():
        raise DatasetError("The CSV has duplicate column names: "
                           + ", ".join(df.columns[df.columns.duplicated()].unique()))
    if len(df) == 0:
        raise DatasetError("The CSV has a header row but no data rows.")
    return df


def read_csv_path(path) -> pd.DataFrame:
    with open(path, "rb") as fh:
        return read_csv_bytes(fh.read())


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")


def resolve_label_source(mapping: dict, label_source: str) -> str:
    """auto -> use the sentiment column if mapped, else derive from rating, else none."""
    if label_source == "auto":
        if mapping.get("sentiment"):
            return "column"
        if mapping.get("rating"):
            return "rating"
        return "none"
    return label_source


def fact_key(product: str, brand: str, title: str, review: str, date: str | None, rating: float | None) -> str:
    raw = "|".join([product.strip().lower(), brand.strip().lower(), title.strip().lower(),
                    review.strip().lower(), date or "", "" if rating is None else f"{rating:g}"])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def validate_dataframe(df: pd.DataFrame, mapping: dict, label_source: str = "auto") -> dict:
    """Produce a validation report for the given mapping. Does not modify df."""
    errors: list[str] = []
    warnings: list[str] = []
    columns = list(df.columns)

    for field, col in mapping.items():
        if col is not None and col not in columns:
            errors.append(f"Mapped column '{col}' for '{field}' does not exist in the file.")
    for field in REQUIRED_FIELDS:
        if not mapping.get(field):
            errors.append(f"A column for '{field}' (the review text) must be mapped.")

    missing_by_column = {c: int(_blank(df[c]).sum()) for c in columns}
    report: dict[str, Any] = {
        "row_count": int(len(df)),
        "columns": columns,
        "missing_by_column": missing_by_column,
        "mapping": mapping,
    }
    if errors:
        report.update(ok=False, errors=errors, warnings=warnings)
        return report

    get = lambda f: df[mapping[f]] if mapping.get(f) else None  # noqa: E731
    review = get("review")
    empty_reviews = int(_blank(review).sum())
    if empty_reviews:
        warnings.append(f"{empty_reviews} rows have empty review text and will be skipped.")
    if empty_reviews == len(df):
        errors.append("Every row has empty review text.")

    ratings_valid = None
    invalid_ratings = 0
    if mapping.get("rating"):
        raw = get("rating")
        parsed = raw.map(parse_rating)
        ratings_valid = parsed
        invalid_ratings = int((parsed.isna() & ~_blank(raw)).sum())
        if invalid_ratings:
            warnings.append(f"{invalid_ratings} ratings are non-numeric or outside "
                            f"{settings.rating_min:g}-{settings.rating_max:g}; they will be stored as missing.")
        report["rating_distribution"] = {f"{k:g}": int(v) for k, v in parsed.value_counts().sort_index().items()}

    if mapping.get("review_date"):
        raw = get("review_date")
        parsed = parse_dates(raw)
        bad = int((parsed.isna() & ~_blank(raw)).sum())
        if bad:
            warnings.append(f"{bad} dates could not be parsed and will be stored as unknown.")
        if parsed.notna().any():
            report["date_range"] = [parsed.min().date().isoformat(), parsed.max().date().isoformat()]

    source = resolve_label_source(mapping, label_source)
    report["label_source"] = source
    labels = None
    if source == "column":
        if not mapping.get("sentiment"):
            errors.append("Label source is 'column' but no sentiment column is mapped.")
        else:
            labels = get("sentiment").map(normalize_label)
            invalid = int((labels.isna() & ~_blank(get("sentiment"))).sum())
            if invalid:
                warnings.append(f"{invalid} sentiment values are not positive/neutral/negative and will be "
                                "treated as unlabeled (excluded from training).")
            if ratings_valid is not None:
                derived = ratings_valid.map(rating_to_label)
                both = labels.notna() & derived.notna()
                if both.any():
                    agreement = float((labels[both] == derived[both]).mean())
                    report["label_rating_agreement"] = round(agreement, 4)
                    if agreement > 0.99:
                        warnings.append(
                            f"The sentiment column matches the rating rule for {agreement:.1%} of rows, so it is "
                            "most likely rating-derived rather than independently annotated.")
    elif source == "rating":
        if ratings_valid is None:
            errors.append("Label source is 'rating' but no rating column is mapped.")
        else:
            labels = ratings_valid.map(rating_to_label)
            warnings.append("Sentiment labels will be DERIVED from ratings ("
                            + ", ".join(f"{k}: {v}" for k, v in list(rating_rule().items())[:3])
                            + "). These are not independently verified annotations.")
    else:
        warnings.append("No sentiment labels available; reviews can be imported and analysed "
                        "but cannot be used for supervised training.")

    if labels is not None:
        counts = labels.value_counts()
        report["label_distribution"] = {k: int(counts.get(k, 0)) for k in LABELS}
        report["unlabeled_rows"] = int(labels.isna().sum())
        present = [k for k in LABELS if counts.get(k, 0) > 0]
        if len(present) < 2:
            warnings.append("Fewer than two sentiment classes are present; models cannot be trained on this data alone.")

    # duplicates on the same key the ETL uses
    dup_cols = [mapping[f] for f in ["product_name", "brand", "review_title", "review", "review_date", "rating"]
                if mapping.get(f)]
    report["duplicate_rows"] = int(df.duplicated(subset=dup_cols).sum())
    if report["duplicate_rows"]:
        warnings.append(f"{report['duplicate_rows']} duplicate rows will be skipped during import.")
    report["duplicate_review_texts"] = int(review[~_blank(review)].str.strip().str.lower().duplicated().sum())

    report.update(ok=not errors, errors=errors, warnings=warnings)
    return report


def preview_rows(df: pd.DataFrame, n: int = 10) -> list[dict]:
    head = df.head(n).replace({np.nan: None})
    return [{k: (None if v is None else str(v)) for k, v in row.items()} for row in head.to_dict("records")]
