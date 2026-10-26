"""ReviewIQ backend entry point.

Run from the backend folder:
    uvicorn main:app --reload --port 8000
Swagger docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import db as database
from config import settings
from deps import model_service
from routers import analytics, datasets, export, models, predict, reviews, warehouse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("reviewiq")


def startup() -> None:
    database.connect()
    model_service.load()
    if database.state.db is not None and settings.auto_import_sample:
        if database.state.db[database.FACT].count_documents({}) == 0 and settings.sample_data_path.exists():
            try:
                result = datasets.import_sample_dataset(database.state.db)
                log.info("Auto-imported sample dataset: %s reviews", result["etl"]["load"]["inserted"])
            except Exception as exc:  # never block startup
                log.warning("Sample auto-import failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield
    if database.state.client is not None:
        database.state.client.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=("Customer review sentiment analysis (TF-IDF + Logistic Regression / Multinomial Naive Bayes) "
                 "with an ETL pipeline, a logical star schema in MongoDB and OLAP analytics."),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"})


@app.get("/api/health", tags=["Health"], summary="Service, database and model status")
def health():
    return {"status": "ok", "version": settings.version, "storage": database.state.info(),
            "models": {"ready": model_service.ready, "message": model_service.load_error,
                       "trained_at": model_service.metadata.get("trained_at") if model_service.metadata else None}}


@app.post("/api/health/reconnect", tags=["Health"], summary="Retry the MongoDB connection")
def reconnect():
    database.connect()
    return database.state.info()


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}


for r in [datasets.router, reviews.router, models.router, predict.router, analytics.router,
          warehouse.router, export.router]:
    app.include_router(r)
