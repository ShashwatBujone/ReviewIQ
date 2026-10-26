import pandas as pd
import pytest

from services.olap import Filters, cube, dice_cube, drill_down, roll_up, slice_cube


@pytest.fixture()
def sdf(sample_df):
    df = sample_df.copy()
    df["dt"] = pd.to_datetime(df["review_date"], utc=True, errors="coerce", format="mixed")
    df["rating"] = df["rating"].astype(float)
    return df


def test_cube_matches_pandas(loaded_db, sdf):
    rows = cube(loaded_db, ["brand", "sentiment"])["rows"]
    expected = sdf.groupby(["brand", "sentiment"]).size()
    assert {(r["brand"], r["sentiment"]): r["review_count"] for r in rows} == expected.to_dict()
    total = cube(loaded_db, [])["rows"][0]
    assert total["review_count"] == len(sdf)
    assert total["avg_rating"] == round(sdf["rating"].mean(), 3)


def test_rollup_and_drilldown_are_consistent(loaded_db, sdf):
    years = {r["year"]: r["review_count"] for r in roll_up(loaded_db, "date", "year")["rows"]}
    assert years["Unknown"] == int(sdf["dt"].isna().sum())
    assert years[2017] == int((sdf["dt"].dt.year == 2017).sum())
    quarters = drill_down(loaded_db, "date", "year", "2017")["rows"]
    assert all(r["quarter"].startswith("2017-") for r in quarters)
    assert sum(r["review_count"] for r in quarters) == years[2017]
    months = drill_down(loaded_db, "date", "quarter", "2017-Q1")["rows"]
    assert {r["month"] for r in months} <= {"2017-01", "2017-02", "2017-03"}
    assert roll_up(loaded_db, "date", "all")["rows"][0]["review_count"] == len(sdf)
    with pytest.raises(ValueError):
        drill_down(loaded_db, "date", "month")


def test_slice(loaded_db, sdf):
    res = slice_cube(loaded_db, "sentiment", "negative", ["brand"])
    assert {r["brand"]: r["review_count"] for r in res["rows"]} == \
        sdf[sdf["sentiment"] == "negative"].groupby("brand").size().to_dict()
    assert all(r["positive"] == 0 for r in res["rows"])


def test_dice(loaded_db, sdf):
    res = dice_cube(loaded_db, {"brand": ["Amazon"], "sentiment": ["negative", "neutral"], "year": [2016, 2017]},
                    ["year", "sentiment"])
    mask = (sdf["brand"] == "Amazon") & sdf["sentiment"].isin(["negative", "neutral"]) & sdf["dt"].dt.year.isin([2016, 2017])
    assert sum(r["review_count"] for r in res["rows"]) == int(mask.sum())
    with pytest.raises(ValueError):
        dice_cube(loaded_db, {"brand": ["Amazon"]}, ["year"])


def test_filters_and_errors(loaded_db, sdf):
    f = Filters(rating_min=4, date_from="2017-01-01", date_to="2017-03-31")
    n = cube(loaded_db, [], f)["rows"][0]["review_count"]
    m = (sdf["rating"] >= 4) & (sdf["dt"] >= "2017-01-01") & (sdf["dt"] < "2017-04-01")
    assert n == int(m.sum())
    with pytest.raises(ValueError):
        cube(loaded_db, ["colour"])
