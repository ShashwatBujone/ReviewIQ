"""End-to-end API tests against the in-memory store (sample data auto-imported at startup)."""
import io

import pandas as pd

CSV = (b"text,stars,item,maker,when\n"
       b"Love it so much,5,Widget,Acme,2021-01-02\n"
       b"Terrible and broken,1,Widget,Acme,2021-02-03\n"
       b"It is ok I guess,3,Gadget,Acme,2021-02-10\n"
       b"Love it so much,5,Widget,Acme,2021-01-02\n")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["storage"]["mode"] == "memory" and body["storage"]["persistent"] is False


def test_dashboard_after_auto_import(client, sample_df):
    s = client.get("/api/dashboard/stats").json()
    assert s["total_reviews"] == len(sample_df)
    counts = sample_df["sentiment"].value_counts()
    assert s["sentiment"]["positive"] == counts["positive"] and s["sentiment"]["negative"] == counts["negative"]
    assert abs(s["avg_rating"] - sample_df["rating"].astype(float).mean()) < 1e-3


def test_predict_before_training_returns_409(client):
    from deps import model_service
    if model_service.ready:  # another test already trained
        return
    r = client.post("/api/predict", json={"text": "great"})
    assert r.status_code == 409


def test_train_and_predict(client):
    r = client.post("/api/models/train", json={"cv_folds": 3})
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["best_model"] in ("logistic_regression", "naive_bayes")
    r = client.post("/api/predict", json={"text": "Stopped working after two days, waste of money"})
    assert r.status_code == 200
    p = r.json()
    assert set(p["predictions"]) == {"logistic_regression", "naive_bayes"} and p["saved"]
    assert client.get("/api/models/evaluation").status_code == 200
    assert len(client.get("/api/models/runs").json()) >= 1
    assert len(client.get("/api/predict/history").json()) >= 1
    assert client.post("/api/predict", json={"text": ""}).status_code == 422
    assert client.post("/api/predict", json={"text": "!!!"}).status_code == 422
    assert client.post("/api/predict", json={"text": "ok", "model": "svm"}).status_code == 422


def test_batch_predict(client):
    client.post("/api/models/train", json={"cv_folds": 0})
    r = client.post("/api/predict/batch", files={"file": ("b.csv", CSV, "text/csv")}, data={"model": "naive_bayes"})
    assert r.status_code == 200
    out = pd.read_csv(io.StringIO(r.text))
    assert {"predicted_sentiment", "prediction_confidence"} <= set(out.columns) and len(out) == 4


def test_upload_validate_import_delete(client):
    before = client.get("/api/dashboard/stats").json()["total_reviews"]
    r = client.post("/api/datasets/upload", files={"file": ("mine.csv", CSV, "text/csv")})
    assert r.status_code == 201, r.text
    ds = r.json()
    assert ds["suggested_mapping"]["review"] == "text" and ds["suggested_mapping"]["brand"] == "maker"
    assert ds["validation"]["label_source"] == "rating" and ds["validation"]["duplicate_rows"] == 1
    assert len(ds["preview"]) == 4

    bad = client.post(f"/api/datasets/{ds['_id']}/validate", json={"mapping": {"rating": "stars"}})
    assert bad.status_code == 200 and not bad.json()["ok"]
    assert client.post(f"/api/datasets/{ds['_id']}/import", json={"mapping": {"rating": "stars"}}).status_code == 422

    r = client.post(f"/api/datasets/{ds['_id']}/import", json={"label_source": "rating"})
    assert r.status_code == 200, r.text
    etl = r.json()
    assert etl["load"]["inserted"] == 3 and etl["transform"]["duplicates_in_file"] == 1
    assert client.get("/api/dashboard/stats").json()["total_reviews"] == before + 3
    found = client.get("/api/reviews", params={"brand": "Acme"}).json()
    assert found["total"] == 3 and {i["sentiment_source"] for i in found["items"]} == {"rating_derived"}

    listing = client.get("/api/datasets").json()
    assert any(d["_id"] == ds["_id"] and d["reviews_in_warehouse"] == 3 for d in listing)
    r = client.delete(f"/api/datasets/{ds['_id']}")
    assert r.status_code == 200 and r.json()["reviews_removed"] == 3
    assert client.get("/api/dashboard/stats").json()["total_reviews"] == before


def test_upload_rejections(client):
    assert client.post("/api/datasets/upload", files={"file": ("x.txt", b"a", "text/plain")}).status_code == 415
    assert client.post("/api/datasets/upload", files={"file": ("x.csv", b"", "text/csv")}).status_code == 422
    assert client.post("/api/datasets/upload", files={"file": ("x.csv", b"a,b\n", "text/csv")}).status_code == 422
    assert client.get("/api/datasets/doesnotexist").status_code == 404


def test_reviews_search_filter_paginate(client, sample_df):
    r = client.get("/api/reviews", params={"page_size": 7, "page": 2, "sort": "rating", "order": "asc"}).json()
    assert r["page"] == 2 and len(r["items"]) == 7 and r["total"] == len(sample_df)
    neg = client.get("/api/reviews", params={"sentiment": "negative", "page_size": 200}).json()
    assert neg["total"] == (sample_df["sentiment"] == "negative").sum()
    s = client.get("/api/reviews", params={"search": "battery"}).json()
    expected = (sample_df["review"].str.contains("battery", case=False) | sample_df["review_title"].str.contains("battery", case=False)
                | sample_df["product_name"].str.contains("battery", case=False)
                | sample_df["brand"].str.contains("battery", case=False)).sum()
    assert s["total"] == expected
    assert client.get("/api/reviews", params={"sort": "nope"}).status_code == 422
    opts = client.get("/api/reviews/filters").json()
    assert set(opts["brands"]) == set(sample_df["brand"])
    one = r["items"][0]["_id"]
    assert client.get(f"/api/reviews/{one}").status_code == 200
    assert client.get("/api/reviews/missing").status_code == 404


def test_analytics_and_olap_endpoints(client, sample_df):
    a = client.get("/api/analytics/summary", params={"granularity": "year", "brand": "Moshi"}).json()
    assert a["overall"]["review_count"] == (sample_df["brand"] == "Moshi").sum()
    assert client.get("/api/warehouse/olap/rollup", params={"hierarchy": "product", "level": "brand"}).status_code == 200
    d = client.get("/api/warehouse/olap/drilldown", params={"hierarchy": "product", "level": "brand", "member": "Moshi"}).json()
    assert sum(r["review_count"] for r in d["rows"]) == (sample_df["brand"] == "Moshi").sum()
    s = client.post("/api/warehouse/olap/slice", json={"dimension": "year", "value": "2017", "group_by": ["sentiment"]})
    assert s.status_code == 200 and s.json()["pipeline"][0]["$match"]["year"] == {"$in": [2017]}
    assert client.post("/api/warehouse/olap/dice", json={"selections": {"brand": ["Amazon"]}, "group_by": []}).status_code == 422
    assert client.get("/api/warehouse/olap/rollup", params={"hierarchy": "x"}).status_code == 422
    c = client.post("/api/warehouse/cube", json={"group_by": ["rating"], "sort_by": "count", "limit": 2}).json()
    assert len(c["rows"]) == 2 and c["rows"][0]["review_count"] >= c["rows"][1]["review_count"]
    sch = client.get("/api/warehouse/schema").json()
    assert sch["counts"]["fact_reviews"] == len(sample_df) and "LOGICAL" in sch["note"]
    assert client.get("/api/warehouse/etl-runs").json()[0]["status"] == "success"


def test_exports(client, sample_df):
    r = client.get("/api/export/reviews", params={"brand": "Moshi"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    df = pd.read_csv(io.StringIO(r.text.lstrip("﻿")))
    assert len(df) == (sample_df["brand"] == "Moshi").sum()
    assert client.get("/api/export/predictions").status_code == 200
    client.post("/api/models/train", json={"cv_folds": 0})
    m = pd.read_csv(io.StringIO(client.get("/api/export/model-metrics").text.lstrip("﻿")))
    assert set(m["model"]) == {"Logistic Regression", "Multinomial Naive Bayes"}


def test_reset_requires_confirm(client):
    assert client.post("/api/warehouse/reset").status_code == 400
