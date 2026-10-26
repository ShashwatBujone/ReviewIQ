"""OLAP-style analytics over the fact_reviews collection using MongoDB aggregation pipelines.

Every function returns the exact pipeline it executed, so the UI can show students what
ran against the database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from db import FACT
from services.preprocessing import LABELS

# Dimension name -> field on the fact document
DIMENSIONS: dict[str, str] = {
    "year": "year",
    "quarter": "quarter_label",
    "month": "year_month",
    "brand": "brand",
    "product": "product_name",
    "sentiment": "sentiment",
    "rating": "rating",
}

# Concept hierarchies used for roll-up / drill-down (coarse -> fine)
HIERARCHIES: dict[str, list[str]] = {
    "date": ["year", "quarter", "month"],
    "product": ["brand", "product"],
    "sentiment": ["sentiment", "rating"],
}

UNKNOWN = "Unknown"


@dataclass
class Filters:
    brand: list[str] = field(default_factory=list)
    product: list[str] = field(default_factory=list)
    sentiment: list[str] = field(default_factory=list)
    rating: list[float] = field(default_factory=list)
    year: list[int] = field(default_factory=list)
    quarter: list[str] = field(default_factory=list)
    month: list[str] = field(default_factory=list)
    rating_min: float | None = None
    rating_max: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    search: str | None = None

    @classmethod
    def from_dict(cls, d: dict | None) -> "Filters":
        d = d or {}
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and v not in (None, "", [])}
        return cls(**known)

    def describe(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", [])}


def _sentiment_values(values: list[str]) -> list[Any]:
    return [None if v in ("unlabeled", UNKNOWN.lower(), "none") else v for v in values]


def build_match(f: Filters) -> dict:
    m: dict[str, Any] = {}
    if f.brand:
        m["brand"] = {"$in": f.brand}
    if f.product:
        m["product_name"] = {"$in": f.product}
    if f.sentiment:
        m["sentiment"] = {"$in": _sentiment_values(f.sentiment)}
    if f.year:
        m["year"] = {"$in": [int(y) for y in f.year]}
    if f.quarter:
        m["quarter_label"] = {"$in": f.quarter}
    if f.month:
        m["year_month"] = {"$in": f.month}
    rating: dict[str, Any] = {}
    if f.rating:
        rating["$in"] = [float(r) for r in f.rating]
    if f.rating_min is not None:
        rating["$gte"] = float(f.rating_min)
    if f.rating_max is not None:
        rating["$lte"] = float(f.rating_max)
    if rating:
        m["rating"] = rating
    date: dict[str, Any] = {}
    if f.date_from:
        date["$gte"] = f.date_from[:10]
    if f.date_to:
        date["$lte"] = f.date_to[:10]
    if date:
        m["review_date"] = date
    if f.search:
        rx = {"$regex": re.escape(f.search.strip()), "$options": "i"}
        m["$or"] = [{"review": rx}, {"review_title": rx}, {"product_name": rx}, {"brand": rx}]
    return m


def _measures() -> dict:
    g: dict[str, Any] = {"review_count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"},
                         "avg_review_length": {"$avg": "$review_length"}}
    for lab in LABELS:
        g[lab] = {"$sum": {"$cond": [{"$eq": ["$sentiment", lab]}, 1, 0]}}
    return g


def _finalize(row: dict, dims: list[str]) -> dict:
    out: dict[str, Any] = {}
    key = row.get("_id") or {}
    for d in dims:
        v = key.get(d) if isinstance(key, dict) else None
        if d == "sentiment" and v is None:
            v = "unlabeled"
        out[d] = UNKNOWN if v is None else v
    out["review_count"] = row["review_count"]
    out["avg_rating"] = None if row.get("avg_rating") is None else round(row["avg_rating"], 3)
    out["avg_review_length"] = None if row.get("avg_review_length") is None else round(row["avg_review_length"], 1)
    labeled = 0
    for lab in LABELS:
        out[lab] = row.get(lab, 0)
        labeled += out[lab]
    out["unlabeled"] = row["review_count"] - labeled
    out["positive_pct"] = round(100 * out["positive"] / labeled, 2) if labeled else None
    out["negative_pct"] = round(100 * out["negative"] / labeled, 2) if labeled else None
    return out


def _sort_key(dims: list[str]):
    def key(r):
        parts = []
        for d in dims:
            v = r[d]
            unknown = v == UNKNOWN
            parts.append((unknown, "" if unknown else (v if isinstance(v, str) else f"{v:012.3f}")))
        return parts
    return key


def cube(db, group_by: list[str], filters: Filters | None = None, sort_by: str | None = None,
         limit: int | None = None) -> dict:
    """Aggregate measures grouped by the given dimensions with optional filters."""
    filters = filters or Filters()
    for d in group_by:
        if d not in DIMENSIONS:
            raise ValueError(f"Unknown dimension '{d}'. Valid: {', '.join(DIMENSIONS)}")
    match = build_match(filters)
    group = {"_id": {d: f"${DIMENSIONS[d]}" for d in group_by} if group_by else None, **_measures()}
    pipeline: list[dict] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.append({"$group": group})
    rows = [_finalize(r, group_by) for r in db[FACT].aggregate(pipeline)]
    if sort_by == "count":
        rows.sort(key=lambda r: -r["review_count"])
    else:
        rows.sort(key=_sort_key(group_by))
    total = len(rows)
    if limit:
        rows = rows[:limit]
    # Present the pipeline as Mongo shell-style JSON (sort/limit are applied in Python for
    # consistent ordering of 'Unknown' members).
    return {"group_by": group_by, "filters": filters.describe(), "pipeline": pipeline,
            "rows": rows, "total_groups": total}


# ----------------------------------------------------------------------------- OLAP operations
def _check_level(hierarchy: str, level: str) -> list[str]:
    if hierarchy not in HIERARCHIES:
        raise ValueError(f"Unknown hierarchy '{hierarchy}'. Valid: {', '.join(HIERARCHIES)}")
    levels = HIERARCHIES[hierarchy]
    if level not in levels and level != "all":
        raise ValueError(f"Level '{level}' is not in the {hierarchy} hierarchy {levels} (or 'all').")
    return levels


def roll_up(db, hierarchy: str, level: str, filters: Filters | None = None) -> dict:
    """Aggregate up a concept hierarchy, e.g. month -> quarter -> year -> all."""
    levels = _check_level(hierarchy, level)
    group = [] if level == "all" else [level]
    res = cube(db, group, filters)
    idx = len(levels) if level == "all" else levels.index(level)
    res.update(operation="roll-up", hierarchy=hierarchy, level=level,
               path=levels[:idx + 1] if level != "all" else ["all"],
               coarser=None if level == "all" else (levels[idx - 1] if idx > 0 else "all"),
               finer=levels[0] if level == "all" else (levels[idx + 1] if idx + 1 < len(levels) else None),
               description=f"Measures summarised at the '{level}' level of the {hierarchy} hierarchy "
                           f"({' > '.join(['all'] + levels)}).")
    return res


def drill_down(db, hierarchy: str, level: str, member: str | None = None,
               filters: Filters | None = None) -> dict:
    """Move from `level` to the next finer level, optionally restricted to one member of `level`."""
    levels = _check_level(hierarchy, level)
    filters = filters or Filters()
    if level == "all":
        child = levels[0]
    else:
        i = levels.index(level)
        if i + 1 >= len(levels):
            raise ValueError(f"'{level}' is already the finest level of the {hierarchy} hierarchy.")
        child = levels[i + 1]
        if member not in (None, ""):
            current = getattr(filters, level, None)
            value: Any = member
            if level == "year":
                value = int(member)
            elif level == "rating":
                value = float(member)
            if isinstance(current, list):
                setattr(filters, level, [value])
    res = cube(db, [child], filters)
    res.update(operation="drill-down", hierarchy=hierarchy, from_level=level, to_level=child, member=member,
               description=f"Drilled down from {level}{' = ' + str(member) if member else ''} to {child}.")
    return res


def slice_cube(db, dimension: str, value: Any, group_by: list[str], filters: Filters | None = None) -> dict:
    """Fix ONE dimension to a single value and analyse the remaining sub-cube."""
    filters = filters or Filters()
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unknown dimension '{dimension}'.")
    if dimension in group_by:
        raise ValueError("The sliced dimension cannot also be a group-by dimension.")
    if dimension == "year":
        value = int(value)
    elif dimension == "rating":
        value = float(value)
    setattr(filters, dimension, [value])
    res = cube(db, group_by, filters)
    res.update(operation="slice", slice={dimension: value},
               description=f"Slice where {dimension} = {value}, grouped by {', '.join(group_by) or 'nothing'}.")
    return res


def dice_cube(db, selections: dict[str, list], group_by: list[str], filters: Filters | None = None) -> dict:
    """Select a sub-cube with value sets on TWO OR MORE dimensions."""
    filters = filters or Filters()
    active = {k: v for k, v in selections.items() if v}
    if len(active) < 2:
        raise ValueError("Dice needs value selections on at least two dimensions.")
    for dim, values in active.items():
        if dim not in DIMENSIONS:
            raise ValueError(f"Unknown dimension '{dim}'.")
        if dim == "year":
            values = [int(v) for v in values]
        elif dim == "rating":
            values = [float(v) for v in values]
        setattr(filters, dim, list(values))
    res = cube(db, group_by, filters)
    res.update(operation="dice", selections=active,
               description="Dice on " + "; ".join(f"{k} in {v}" for k, v in active.items())
                           + f", grouped by {', '.join(group_by) or 'nothing'}.")
    return res
