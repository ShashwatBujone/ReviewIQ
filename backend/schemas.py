"""Pydantic request models (validated automatically and documented in Swagger)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    review: str | None = Field(None, description="Column holding the review text (required)")
    review_title: str | None = None
    rating: str | None = None
    product_name: str | None = None
    brand: str | None = None
    review_date: str | None = None
    sentiment: str | None = None


LabelSource = Literal["auto", "column", "rating", "none"]


class ValidateRequest(BaseModel):
    mapping: ColumnMapping
    label_source: LabelSource = "auto"


class ImportRequest(BaseModel):
    mapping: ColumnMapping | None = Field(None, description="Defaults to the suggested mapping")
    label_source: LabelSource = Field("auto", description="auto = sentiment column if mapped, else rating-derived")
    mode: Literal["append", "replace"] = Field("append", description="replace clears existing reviews first")


class TrainRequest(BaseModel):
    test_size: float = Field(0.2, ge=0.1, le=0.5)
    random_state: int = 42
    include_title: bool = Field(True, description="Prepend the review title to the review text")
    deduplicate: bool = Field(True, description="Drop duplicate texts before splitting (prevents leakage)")
    balance_classes: bool = Field(True, description="Re-weight classes to counter imbalance")
    max_features: int = Field(20000, ge=100, le=200000)
    ngram_max: int = Field(2, ge=1, le=3)
    lr_C: float = Field(1.0, gt=0, le=100)
    nb_alpha: float = Field(0.1, gt=0, le=10, description="Default chosen by cross-validation on the sample data")
    cv_folds: int = Field(5, ge=0, le=10)
    dataset_id: str | None = Field(None, description="Train only on reviews from this dataset")


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    model: Literal["both", "logistic_regression", "naive_bayes"] = "both"
    save: bool = True


class SliceRequest(BaseModel):
    dimension: str = Field(..., examples=["sentiment"])
    value: str | int | float = Field(..., examples=["negative"])
    group_by: list[str] = Field(default_factory=lambda: ["product"])
    filters: dict = Field(default_factory=dict)


class DiceRequest(BaseModel):
    selections: dict[str, list[str | int | float]] = Field(
        ..., examples=[{"brand": ["Amazon"], "sentiment": ["negative", "neutral"], "year": [2016, 2017]}])
    group_by: list[str] = Field(default_factory=lambda: ["year", "sentiment"])
    filters: dict = Field(default_factory=dict)


class CubeRequest(BaseModel):
    group_by: list[str] = Field(default_factory=lambda: ["brand", "sentiment"])
    filters: dict = Field(default_factory=dict)
    sort_by: Literal["dimension", "count"] = "dimension"
    limit: int | None = Field(None, ge=1, le=5000)
