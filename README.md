# ReviewIQ — Customer Review Sentiment Analysis and Data Warehouse Analytics

ReviewIQ is a full-stack Data Warehousing & Mining project. It loads customer reviews through an
**ETL pipeline** into a **logical star schema in MongoDB**, runs **OLAP operations** (roll-up,
drill-down, slice, dice) with MongoDB aggregation pipelines, and trains two **sentiment
classifiers** (TF-IDF + Logistic Regression, TF-IDF + Multinomial Naive Bayes) whose real
evaluation results are shown in a React dashboard.

Everything runs locally on your laptop — no website builder or hosted service is needed.

---

## Contents

1. [Features](#1-features)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Quick start on Windows](#4-quick-start-on-windows)
5. [Configuring MongoDB](#5-configuring-mongodb)
6. [Manual installation and start-up](#6-manual-installation-and-start-up)
7. [Importing a dataset](#7-importing-a-dataset)
8. [Training and comparing models](#8-training-and-comparing-models)
9. [Predictions and OLAP operations](#9-predictions-and-olap-operations)
10. [API reference](#10-api-reference)
11. [Running the tests](#11-running-the-tests)
12. [Troubleshooting](#12-troubleshooting)
13. [Project structure](#13-project-structure)
14. [Methodology notes and limitations](#14-methodology-notes-and-limitations)

---

## 1. Features

| Page | What it does |
|------|--------------|
| **Dashboard** | Total reviews, sentiment distribution, average rating, rating histogram, monthly sentiment trend, most-reviewed products, current model score vs. baseline, recent activity (ETL runs, training runs, predictions). |
| **Sentiment Analyzer** | Predict the sentiment of any text with one or both models, with class probabilities, the cleaned text and how many words the model recognised. Prediction history (saved to MongoDB, exportable). Batch prediction: upload a CSV, download it with predicted labels. |
| **Reviews Explorer** | Searchable, filterable (brand, product, sentiment, rating, date range), sortable, paginated table; expandable rows; CSV export of the current filter. |
| **Dataset Management** | Upload a CSV → validation report (missing values, invalid ratings, unparseable dates, duplicates, label distribution) → **column-mapping UI** → choose label source → run ETL (append or replace). Import/download the bundled sample, delete datasets, reset the warehouse. |
| **Model Performance** | Train with adjustable parameters; accuracy, precision, recall, F1 (macro & weighted), k-fold CV, confusion matrices, per-class metrics, most indicative terms, majority-class baseline, training history, metrics CSV. |
| **Insights & Analytics** | Sentiment by product, brand, rating and time (year / quarter / month), all filterable. |
| **Data Warehouse** | Star-schema diagram with live document counts, sample fact document, ETL run history, and an **OLAP workbench** (roll-up & drill-down navigator, slice, dice, custom cube) that shows the exact aggregation pipeline executed. |
| **About Project** | Objectives, stack, algorithms (with formulas), methodology and honest-reporting principles. |

## 2. Architecture

```
 ┌──────────────────────────┐   HTTP/JSON    ┌──────────────────────────────────────────┐
 │ React + Vite (port 5173) │ ─────────────► │ FastAPI (port 8000)   /docs = Swagger UI │
 │ Recharts, React Router   │ ◄───────────── │                                          │
 └──────────────────────────┘                │  routers/   datasets · reviews · models  │
                                             │             predict · analytics          │
                                             │             warehouse · export           │
                                             │  services/  preprocessing · etl · ml     │
                                             │             olap                         │
                                             └───────┬──────────────────────┬───────────┘
                                                     │ PyMongo              │ joblib
                                         ┌───────────▼───────────┐   ┌──────▼─────────────┐
                                         │ MongoDB (db reviewiq) │   │ backend/models/    │
                                         │ fact_reviews          │   │ tfidf_vectorizer   │
                                         │ dim_product dim_brand │   │ logistic_regression│
                                         │ dim_date dim_sentiment│   │ naive_bayes        │
                                         │ datasets etl_runs     │   │ model_metadata.json│
                                         │ model_runs predictions│   └────────────────────┘
                                         └───────────────────────┘
```

**Logical star schema** (implemented with MongoDB collections, not relational tables):

```
            dim_product (product_key, product_name, brand)        dim_date (date_key, date, year, quarter, month, …)
                         \                                          /
                          \                                        /
                           ───────────  fact_reviews  ─────────────
                          /   keys: product_key, brand_key,        \
                         /          date_key, sentiment_key          \
            dim_brand (brand_key, brand)   measures: rating, review_length,   dim_sentiment (sentiment_key, label, rule)
                                           sentiment counts
```

Dimension attributes (brand, product name, year, quarter, month) are also **denormalised** onto
each fact document so that the OLAP aggregation pipelines do not need `$lookup` joins. This is a
standard document-database design choice; MongoDB is not a relational database.

## 3. Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Python | **3.10 – 3.14, ideally 3.13** (tested with 3.13). Newer versions may lack pre-built packages. | https://www.python.org/downloads/ (tick **“Add python.exe to PATH”**) or `py install 3.13` |
| Node.js | 18 or newer LTS (tested with 22) | https://nodejs.org/ |
| MongoDB Community Server *(recommended)* | 6.0+ | https://www.mongodb.com/try/download/community — or use free MongoDB Atlas |

MongoDB is the primary database. If it is not running, the backend can start in a clearly-labelled
**demo mode** that keeps data in a temporary in-memory store (see section 5).

## 4. Quick start on Windows

1. Extract `ReviewIQ_Complete_Project.zip`, e.g. to `C:\Projects\ReviewIQ`.
2. Make sure MongoDB is running (section 5) — optional but recommended.
3. Double-click **`setup.bat`** (one time). It creates `backend\.venv`, installs the Python
   packages, runs `npm install`, and creates `backend\.env` and `frontend\.env` from the examples.
4. Double-click **`start-all.bat`**. Two terminal windows open (API and web app) and your browser
   opens http://localhost:5173.

On first start, if the warehouse is empty, the bundled sample dataset (997 reviews) is imported
automatically (`AUTO_IMPORT_SAMPLE=true`). Pre-trained models from that sample are included in
`backend\models\`, so predictions work immediately; you can retrain at any time.

## 5. Configuring MongoDB

All settings live in `backend\.env` (copy of `backend\.env.example`).

**Option A — local MongoDB (Windows)**

1. Install *MongoDB Community Server* with the default “Install as a Service” option.
2. The service starts automatically. To start it manually, open *Command Prompt as administrator*:
   ```bat
   net start MongoDB
   ```
3. Keep the default in `backend\.env`:
   ```ini
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB=reviewiq
   ```
4. Optional: install *MongoDB Compass* to browse the `reviewiq` database and its collections.

**Option B — MongoDB Atlas (cloud, free tier)**

1. Create a free cluster at https://www.mongodb.com/cloud/atlas, add a database user, and allow
   your IP address under *Network Access*.
2. Copy the connection string (*Connect → Drivers*) into `backend\.env`:
   ```ini
   MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

**Demo mode.** With `DEMO_MODE=true` (default), if MongoDB cannot be reached the API falls back to
an in-memory store (mongomock). The UI shows a yellow *Demo mode* banner and `/api/health` reports
`"mode": "memory", "persistent": false` — data is **not** written to MongoDB and is lost when the
backend stops. Start MongoDB and press **Reconnect** in the banner (or restart the backend).
Set `DEMO_MODE=false` to require MongoDB; the API then returns HTTP 503 with setup instructions.

Indexes are created automatically on start-up (sentiment, brand, product, rating, date keys,
year-month, dataset, compound brand + sentiment, and timestamps on the log collections).

## 6. Manual installation and start-up

Use these if you prefer typing the commands (Command Prompt, from the project folder):

```bat
:: ---- backend ----
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --port 8000
```

```bat
:: ---- frontend (second terminal) ----
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 (web app) and http://localhost:8000/docs (API documentation).

PowerShell users: activate the environment with `.venv\Scripts\Activate.ps1` (you may need
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once) and use `Copy-Item` instead of `copy`.

The frontend reads the backend URL from `frontend\.env` → `VITE_API_URL=http://localhost:8000`.
If you change the backend port, update this value and `CORS_ORIGINS` in `backend\.env`.

A production build of the frontend can be made with `npm run build` (output in `frontend\dist`).

## 7. Importing a dataset

1. Open **Dataset Management**.
2. Drag a CSV onto the upload box (or click **Import sample dataset**).
3. Review the validation report: row count, missing values per column, invalid ratings,
   unparseable dates, duplicate rows, label distribution and warnings.
4. Check the **column mapping**. Columns are auto-detected from common names
   (`review`, `text`, `reviews.text`, `rating`, `stars`, `product_name`, `name`, `brand`,
   `manufacturer`, `review_date`, `date`, `sentiment`, `label`, …). Only the review-text column
   is required.
5. Choose the **label source**:
   * **Auto** – use the sentiment column if mapped, otherwise derive from rating.
   * **Sentiment column** – values `positive / neutral / negative` (also `pos/neu/neg`).
   * **Derive from rating** – `≤ 2 → negative`, `3 → neutral`, `≥ 4 → positive` (configurable
     with `RATING_NEGATIVE_MAX` / `RATING_POSITIVE_MIN`). These are rating-derived proxy labels,
     **not** verified sentiment annotations, and are marked `rating_derived` on every record.
   * **No labels** – import for analytics only.
6. Choose **Append** (skip reviews already in the warehouse) or **Replace**, then **Run ETL import**.

ETL details: empty reviews are skipped; invalid ratings (non-numeric or outside 1–5) are stored as
missing; unparseable dates go to the *Unknown* date member (`date_key = 0`); exact duplicates
(same product, brand, title, text, date and rating) are removed within the file and against the
warehouse; dimensions are rebuilt after every load; every run is logged in `etl_runs`.

**About the bundled sample** (`data/sample/customer_reviews_preprocessed.csv`, 997 rows, 8 columns:
product_name, brand, review_date, review_title, review, cleaned_review, rating, sentiment):
the validation report shows that its `sentiment` column agrees with the rating rule for 100% of
rows, so its labels are effectively rating-derived. 106 rows have no date, 62 products and 2
brands are present, and classes are imbalanced (844 positive, 79 neutral, 74 negative). The
provided `cleaned_review` column is not used for modelling; the app re-cleans the raw `review`
text with its own pipeline so that training and live prediction use identical preprocessing.

## 8. Training and comparing models

Open **Model Performance**, adjust parameters if you wish, and click **Train & evaluate**
(or call `POST /api/models/train`, or run `python train_models.py` inside `backend`).

Pipeline:

1. Take all reviews with a valid label (others are excluded and counted).
2. Build the model text (title + review) and clean it (lower-case, expand contractions, remove
   URLs/HTML/e-mails/digits/punctuation, remove stop-words but keep negations).
3. Remove exact duplicate texts, so one text cannot appear in both train and test sets.
4. Stratified train/test split (default 80/20, seed 42).
5. Fit TF-IDF (unigrams + bigrams, sub-linear tf, min_df 2) on the **training split only**.
6. Train Logistic Regression (`class_weight="balanced"`) and Multinomial Naive Bayes (balanced
   sample weights).
7. Stratified k-fold cross-validation on the training split; select the best model by
   cross-validated macro F1, so the test set is used only for the final report.
8. Evaluate on the test split: accuracy, macro/weighted precision, recall, F1, per-class metrics,
   confusion matrix, and the majority-class baseline.
9. Save the vectoriser and models with joblib (`backend/models/`) and log the run in `model_runs`.

Results of the shipped models (sample data, default settings; your run will reproduce them with
the same data, seed and library versions):

| Test set (182 reviews: 154 pos / 14 neu / 14 neg) | Accuracy | Macro precision | Macro recall | Macro F1 | 5-fold CV macro F1 (train) |
|---|---|---|---|---|---|
| Majority-class baseline (always “positive”) | 0.846 | – | – | 0.306 | – |
| Logistic Regression | 0.852 | 0.613 | 0.617 | 0.613 | 0.452 ± 0.032 |
| Multinomial Naive Bayes | 0.819 | 0.549 | 0.604 | 0.571 | 0.521 ± 0.044 |

How to read this: accuracy is barely above the “always positive” baseline, so macro F1 is the
meaningful number. Both models clearly beat the baseline on macro F1, but the neutral and negative
classes have only ~70 training examples each, so their scores are modest and vary between
splits (note the gap between CV and test F1). Naive Bayes is *selected* because it has the higher
cross-validated F1, even though Logistic Regression scored higher on this particular test split —
a useful discussion point about model selection and small-sample variance.

## 9. Predictions and OLAP operations

**Predictions** — *Sentiment Analyzer* page, or:

```bat
curl -X POST http://localhost:8000/api/predict -H "Content-Type: application/json" ^
     -d "{\"text\": \"Stopped working after a week, waste of money\", \"model\": \"both\"}"
```

The response contains each model's label, class probabilities (`predict_proba`) and confidence
(the highest probability — an estimate, not a calibrated guarantee), the cleaned text, and
`known_terms`. If none of the words were seen in training, a warning explains that the prediction
only reflects class priors. Batch prediction: `POST /api/predict/batch` (multipart CSV).

**OLAP** — *Data Warehouse → OLAP workbench*, or via the API:

| Operation | Example | Meaning |
|-----------|---------|---------|
| Roll-up | `GET /api/warehouse/olap/rollup?hierarchy=date&level=year` | Aggregate month → quarter → year → all (`level=all` gives the grand total). Hierarchies: `date` (year→quarter→month), `product` (brand→product), `sentiment` (sentiment→rating). |
| Drill-down | `GET /api/warehouse/olap/drilldown?hierarchy=date&level=year&member=2017` | Break 2017 into its quarters (then `level=quarter&member=2017-Q1` into months). |
| Slice | `POST /api/warehouse/olap/slice` `{"dimension":"sentiment","value":"negative","group_by":["product"]}` | Fix one dimension and analyse the rest. |
| Dice | `POST /api/warehouse/olap/dice` `{"selections":{"brand":["Amazon"],"sentiment":["negative","neutral"],"year":[2016,2017]},"group_by":["year","sentiment"]}` | Select value sets on ≥ 2 dimensions. |
| Cube | `POST /api/warehouse/cube` `{"group_by":["brand","sentiment"],"filters":{"rating_min":4}}` | Generic group-by over any dimensions. |

Every OLAP response includes the MongoDB `pipeline` it ran, the result `rows` (review count,
average rating, average length, positive/neutral/negative counts, positive %), and a description.

## 10. API reference

Interactive documentation: **http://localhost:8000/docs** (Swagger) or `/redoc`.

| Method & path | Purpose |
|---|---|
| `GET /api/health`, `POST /api/health/reconnect` | Service, storage mode and model status; retry MongoDB |
| `POST /api/datasets/upload` | Upload CSV → validation + suggested mapping + preview (201) |
| `GET /api/datasets`, `GET /api/datasets/{id}` | List / inspect datasets |
| `POST /api/datasets/{id}/validate` | Re-validate with a custom mapping and label source |
| `POST /api/datasets/{id}/import` | Run the ETL (`mapping`, `label_source`, `mode`) |
| `DELETE /api/datasets/{id}` | Delete a dataset and the reviews it loaded |
| `POST /api/datasets/sample/import`, `GET /api/datasets/sample/download` | Bundled sample |
| `GET /api/reviews` | Search / filter / sort / paginate (`search, brand, product, sentiment, rating, year, rating_min, rating_max, date_from, date_to, page, page_size, sort, order`) |
| `GET /api/reviews/filters`, `GET /api/reviews/{id}` | Filter options; single review |
| `POST /api/models/train` | Train and evaluate both models |
| `GET /api/models/status`, `/evaluation`, `/runs` | Model status, current metrics, history |
| `POST /api/predict`, `POST /api/predict/batch` | Single / batch prediction |
| `GET /api/predict/history`, `DELETE /api/predict/history` | Prediction history |
| `GET /api/dashboard/stats` | Dashboard numbers |
| `GET /api/analytics/summary` | Sentiment by product, brand, rating, time (same filters + `granularity`, `top_n`) |
| `GET /api/warehouse/schema`, `/etl-runs` | Star schema with live counts; ETL history |
| `POST /api/warehouse/rebuild-dimensions`, `POST /api/warehouse/reset?confirm=true` | Maintenance |
| `GET /api/warehouse/olap/rollup`, `/olap/drilldown`; `POST /olap/slice`, `/olap/dice`, `/cube` | OLAP |
| `GET /api/export/reviews`, `/predictions`, `/model-metrics` | CSV exports (UTF-8 with BOM for Excel) |

Status codes: 400 bad request, 404 not found, 409 models not trained, 413 file too large,
415 not a CSV, 422 validation error, 503 MongoDB unavailable (with `DEMO_MODE=false`).

## 11. Running the tests

```bat
run-tests.bat
```
or manually from the project root:
```bat
backend\.venv\Scripts\activate
python -m pytest -v
```

The 50 tests (`tests/`) use the in-memory store, so MongoDB is not required. They cover text
cleaning, the rating rule, column detection, CSV validation, ETL (duplicates, empty rows, invalid
ratings/dates, append/replace, dimensions), training/evaluation/save/load, OLAP results checked
against independent pandas calculations, and every API endpoint group.

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| Yellow **Demo mode** banner | MongoDB is not reachable. Start it (`net start MongoDB` as admin) or fix `MONGO_URI`, then click **Reconnect**. |
| Red **Backend not reachable** banner | Start the API (`start-backend.bat`). Check `VITE_API_URL` in `frontend\.env` and restart `npm run dev` after editing it. |
| `'python' is not recognized` | Reinstall Python with “Add to PATH”, or use `py -3` instead of `python`. |
| PowerShell blocks `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use Command Prompt. |
| Port 8000 / 5173 already in use | `uvicorn main:app --port 8001` and set `VITE_API_URL=http://localhost:8001`; Vite picks another port automatically — add it to `CORS_ORIGINS`. |
| “Models were saved with scikit-learn X…” | Your scikit-learn version differs from the one that saved the models. Click **Train & evaluate** (or `python train_models.py`). |
| Atlas `ServerSelectionTimeoutError` | Add your IP under *Network Access*, check user/password, and URL-encode special characters in the password. |
| CSV upload says it cannot be decoded | Save the file as *CSV UTF-8* in Excel. UTF-8, UTF-8-BOM and Windows-1252 are supported. |
| Training error “at least two classes” | The imported data has no labels or only one class; map a sentiment or rating column. |
| Want to start from an empty warehouse | Set `AUTO_IMPORT_SAMPLE=false` and use **Reset warehouse** on Dataset Management. |

## 13. Project structure

```
ReviewIQ/
├── backend/
│   ├── main.py                FastAPI app, start-up (DB connect, model load, sample import)
│   ├── config.py              Settings from environment / .env
│   ├── db.py                  MongoDB connection, demo fallback, indexes, collection names
│   ├── deps.py                Shared dependencies (filters, model service, JSON helpers)
│   ├── schemas.py             Pydantic request models
│   ├── train_models.py        Command-line training
│   ├── routers/               datasets, reviews, models, predict, analytics, warehouse, export
│   ├── services/              preprocessing, etl, ml, olap
│   ├── models/                Saved TF-IDF vectoriser, both models, model_metadata.json
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/pages/             Dashboard, Analyzer, Reviews, Datasets, Models, Insights, Warehouse, About
│   ├── src/components/        Layout, FilterBar, shared UI
│   ├── src/api.js             API client (uses VITE_API_URL)
│   ├── package.json, vite.config.js, .env.example
├── data/
│   ├── sample/customer_reviews_preprocessed.csv
│   └── uploads/               Uploaded CSVs are stored here
├── tests/                     pytest suite (50 tests)
├── setup.bat, start-all.bat, start-backend.bat, start-frontend.bat, run-tests.bat
├── pytest.ini, .gitignore, .env.example
└── README.md
```

## 14. Methodology notes and limitations

* No figure in the UI is hard-coded: totals, charts, metrics and predictions are computed from the
  stored data or the trained models at request time.
* Labels in the sample are rating-derived; the models therefore learn to predict *star-rating
  buckets from text*, which is related to — but not the same as — human-judged sentiment.
* Neutral and negative classes are small (≈ 70 training examples each); expect per-class scores
  to vary by a few points between random seeds.
* The demo in-memory store (mongomock) supports the aggregation stages used here but is not a
  substitute for MongoDB; use a real MongoDB server for the project demonstration.
* The star schema is logical: MongoDB stores documents, keys are plain fields, and there are no
  foreign-key constraints.
