#!/usr/bin/env python3
"""FastAPI dashboard API for the Review Analytics tool."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from backend.analyzer import analyze_reviews
    from backend.listing_generator import generate_listing
    from backend.revenue_estimator import estimate_all_products
    from backend.scraper import asin_from_url, normalize_asin, scrape_asins_resilient
except ModuleNotFoundError:
    # Supports deployments where backend/ is the service root.
    from analyzer import analyze_reviews
    from listing_generator import generate_listing
    from revenue_estimator import estimate_all_products
    from scraper import asin_from_url, normalize_asin, scrape_asins_resilient


DB_PATH = "backend/data.db"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
MAIN_ASIN = "B07JZHXXBT"
TRACKED_ASINS = [
    MAIN_ASIN,
    "B000BD0RT0",
    "B07FK237C5",
    "B07QCY5ZYH",
    "B07FK28Z98",
    "B07TWKR3X1",
    "B01HCVVX76",
    "B07FK25HFB",
    "B07FKCKQ9P",
    "B07FK3GJ8Q",
]

app = FastAPI(
    title="Review Analytics Dashboard API",
    version="0.1.0",
    description="Dashboard API for product, criteria, hooks, listings, and scraping jobs.",
)


def allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_ALLOWED_ORIGINS
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed or DEFAULT_ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRAPE_JOBS: dict[str, dict[str, Any]] = {}
SCRAPE_JOBS_LOCK = threading.Lock()
ACTIVE_ASINS = TRACKED_ASINS.copy()
ACTIVE_ASINS_LOCK = threading.Lock()


class ScrapeRequest(BaseModel):
    asins: list[str] = Field(..., min_length=1, max_length=10)


class ScrapeUrlsRequest(BaseModel):
    product_url: str
    competitor_urls: list[str] = Field(default_factory=list, max_length=9)


class ActiveAsinsRequest(BaseModel):
    asins: list[str] = Field(..., min_length=1, max_length=10)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row else None


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def safe_json_loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def ensure_generated_listing_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            title TEXT NOT NULL,
            bullets TEXT NOT NULL,
            description TEXT NOT NULL,
            model TEXT,
            generated_at TEXT NOT NULL,
            input_snapshot TEXT,
            FOREIGN KEY (asin) REFERENCES products (asin)
        )
        """
    )


def ensure_scrape_jobs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scrape_jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            asins TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT
        )
        """
    )


def save_scrape_job(job: dict[str, Any]) -> None:
    with connect() as conn:
        ensure_scrape_jobs_table(conn)
        conn.execute(
            """
            INSERT INTO scrape_jobs (job_id, status, asins, created_at, started_at, completed_at, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status,
                asins = excluded.asins,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                result = excluded.result,
                error = excluded.error
            """,
            (
                job["job_id"],
                job["status"],
                json.dumps(job.get("asins") or []),
                job["created_at"],
                job.get("started_at"),
                job.get("completed_at"),
                json.dumps(job.get("result")) if job.get("result") is not None else None,
                job.get("error"),
            ),
        )
        conn.commit()


def load_scrape_job(job_id: str) -> Optional[dict[str, Any]]:
    with connect() as conn:
        ensure_scrape_jobs_table(conn)
        row = conn.execute(
            """
            SELECT job_id, status, asins, created_at, started_at, completed_at, result, error
            FROM scrape_jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

    if not row:
        return None
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "asins": safe_json_loads(row["asins"], []),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "result": safe_json_loads(row["result"], None),
        "error": row["error"],
    }


def latest_scrape_jobs(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        ensure_scrape_jobs_table(conn)
        rows = conn.execute(
            """
            SELECT job_id, status, asins, created_at, started_at, completed_at, result, error
            FROM scrape_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    jobs: list[dict[str, Any]] = []
    for row in rows:
        jobs.append(
            {
                "job_id": row["job_id"],
                "status": row["status"],
                "asins": safe_json_loads(row["asins"], []),
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "result": safe_json_loads(row["result"], None),
                "error": row["error"],
            }
        )
    return jobs


def extract_asin(value: str) -> str:
    cleaned = value.strip()
    if re.fullmatch(r"[A-Za-z0-9]{10}", cleaned):
        return normalize_asin(cleaned)

    asin = asin_from_url(cleaned)
    if asin:
        return normalize_asin(asin)

    raise ValueError(f"Could not extract an ASIN from: {value}")


def unique_asins_preserve_order(asins: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for asin in asins:
        normalized = normalize_asin(asin)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def current_tracked_asins() -> list[str]:
    with ACTIVE_ASINS_LOCK:
        active_asins = ACTIVE_ASINS.copy()
    if active_asins != TRACKED_ASINS:
        return active_asins

    latest_jobs = latest_scrape_jobs(1)
    latest_asins = latest_jobs[0]["asins"] if latest_jobs else []
    if latest_asins:
        set_active_asins(latest_asins)
        return latest_asins[:10]

    return active_asins


def set_active_asins(asins: list[str]) -> None:
    with ACTIVE_ASINS_LOCK:
        ACTIVE_ASINS.clear()
        ACTIVE_ASINS.extend(asins[:10])


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "review-analytics-dashboard-api"}


@app.get("/api/products")
def get_products() -> list[dict[str, Any]]:
    estimate_all_products(DB_PATH)
    tracked_asins = current_tracked_asins()
    placeholders = ",".join("?" for _ in tracked_asins)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT asin, title, price, rating, review_count, bsr,
                   estimated_units_per_month, estimated_revenue_per_month,
                   revenue_confidence, scraped_at
            FROM products
            WHERE asin IN ({placeholders})
            """,
            tracked_asins,
        ).fetchall()

    rows_by_asin = {row["asin"]: row for row in rows}
    products: list[dict[str, Any]] = []
    for asin in tracked_asins:
        row = rows_by_asin.get(asin)
        title = row["title"] if row else None
        products.append(
            {
                "asin": asin,
                "product": title or f"ASIN {asin}",
                "title": title,
                "price": row["price"] if row else None,
                "rating": row["rating"] if row else None,
                "reviews": row["review_count"] if row else None,
                "review_count": row["review_count"] if row else None,
                "bsr": row["bsr"] if row else None,
                "estimated_units_per_month": row["estimated_units_per_month"] if row else None,
                "revenue": row["estimated_revenue_per_month"] if row else None,
                "estimated_revenue_per_month": row["estimated_revenue_per_month"] if row else None,
                "revenue_confidence": row["revenue_confidence"] if row else None,
                "scraped_at": row["scraped_at"] if row else None,
                "is_main": asin == tracked_asins[0],
                "status": "Scraped" if title else "No product data",
            }
        )
    return products


@app.get("/api/criteria")
def get_criteria() -> list[dict[str, Any]]:
    tracked_asins = current_tracked_asins()
    if not tracked_asins:
        return []
    placeholders = ",".join("?" for _ in tracked_asins)
    with connect() as conn:
        criteria_rows = conn.execute(
            f"""
            SELECT DISTINCT c.id, c.name, c.description, c.mention_count
            FROM criteria c
            JOIN product_scores ps ON ps.criterion_id = c.id
            WHERE ps.asin IN ({placeholders})
            ORDER BY mention_count DESC, id
            LIMIT 5
            """,
            tracked_asins,
        ).fetchall()
        score_rows = conn.execute(
            f"""
            SELECT ps.criterion_id, ps.asin, ps.score, p.title
            FROM product_scores ps
            LEFT JOIN products p ON p.asin = ps.asin
            WHERE ps.asin IN ({placeholders})
            ORDER BY ps.score DESC
            """,
            tracked_asins,
        ).fetchall()

    scores_by_criterion: dict[int, list[dict[str, Any]]] = {}
    for row in score_rows:
        scores_by_criterion.setdefault(row["criterion_id"], []).append(
            {
                "asin": row["asin"],
                "product": row["title"] or row["asin"],
                "score": row["score"],
                "is_main": bool(tracked_asins and row["asin"] == tracked_asins[0]),
            }
        )

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "mentionCount": row["mention_count"],
            "mention_count": row["mention_count"],
            "scores": scores_by_criterion.get(row["id"], []),
        }
        for row in criteria_rows
    ]


@app.get("/api/hooks")
def get_hooks(
    sentiment: Optional[str] = Query(default=None, pattern="^(positive|negative|neutral)$"),
    min_frequency: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    tracked_asins = set(current_tracked_asins())
    filters = ["frequency >= ?"]
    params: list[Any] = [min_frequency]
    if sentiment:
        filters.append("sentiment = ?")
        params.append(sentiment)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, phrase, sentiment, frequency, asins
            FROM hooks
            WHERE {' AND '.join(filters)}
            ORDER BY frequency DESC, phrase
            """,
            params,
        ).fetchall()

    hooks: list[dict[str, Any]] = []
    for row in rows:
        asins = safe_json_loads(row["asins"], [])
        if tracked_asins and not (set(asins) & tracked_asins):
            continue
        hooks.append({
            "id": row["id"],
            "phrase": row["phrase"],
            "sentiment": row["sentiment"],
            "frequency": row["frequency"],
            "asins": asins,
        })
    return hooks


@app.get("/api/listing/{asin}")
def get_listing(asin: str) -> dict[str, Any]:
    normalized_asin = asin.upper()
    with connect() as conn:
        ensure_generated_listing_table(conn)
        product = row_dict(
            conn.execute(
                """
                SELECT asin, title
                FROM products
                WHERE asin = ?
                """,
                (normalized_asin,),
            ).fetchone()
        )
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {normalized_asin} not found")

        generated = row_dict(
            conn.execute(
                """
                SELECT id, title, bullets, description, model, generated_at
                FROM generated_listings
                WHERE asin = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized_asin,),
            ).fetchone()
        )

    current = {
        "title": product["title"] or f"ASIN {normalized_asin}",
        "bullets": [],
        "description": "No current product description is stored yet. Scraper product details can be mapped into this field next.",
    }

    if generated:
        generated_listing = {
            "id": generated["id"],
            "title": generated["title"],
            "bullets": safe_json_loads(generated["bullets"], []),
            "description": generated["description"],
            "model": generated["model"],
            "generated_at": generated["generated_at"],
        }
    else:
        generated_listing = {
            "id": None,
            "title": "",
            "bullets": [],
            "description": "",
            "model": None,
            "generated_at": None,
        }

    return {
        "asin": normalized_asin,
        "current": current,
        "generated": generated_listing,
    }


def run_scrape_job(job_id: str, asins: list[str]) -> None:
    with SCRAPE_JOBS_LOCK:
        SCRAPE_JOBS[job_id].update({"status": "running", "started_at": utc_now_iso()})
        save_scrape_job(SCRAPE_JOBS[job_id])

    try:
        result = scrape_asins_resilient(asins)
        estimate_all_products(DB_PATH)
        pipeline: dict[str, Any] = {
            "scrape": {"status": "completed"},
            "revenue_estimation": {"status": "completed"},
            "analysis": {"status": "skipped"},
            "listing_generation": {"status": "skipped"},
        }

        successful_asins = [
            asin
            for asin, item in result.items()
            if not asin.startswith("_") and isinstance(item, dict) and item.get("product_saved")
        ]

        if successful_asins:
            try:
                analysis_result = analyze_reviews(DB_PATH, asins=successful_asins)
                pipeline["analysis"] = {
                    "status": "completed",
                    "review_count": analysis_result.get("review_count"),
                    "batch_count": analysis_result.get("batch_count"),
                }
            except Exception as exc:
                pipeline["analysis"] = {"status": "failed", "error": str(exc)}

            main_asin = asins[0]
            if main_asin in successful_asins:
                try:
                    listing_result = generate_listing(
                        main_asin,
                        competitor_asins=[asin for asin in asins[1:] if asin in successful_asins],
                        db_path=DB_PATH,
                    )
                    pipeline["listing_generation"] = {
                        "status": "completed",
                        "asin": main_asin,
                        "listing_id": listing_result.get("id"),
                    }
                except Exception as exc:
                    pipeline["listing_generation"] = {"status": "failed", "asin": main_asin, "error": str(exc)}
            else:
                pipeline["listing_generation"] = {
                    "status": "skipped",
                    "reason": f"Main ASIN {main_asin} was not scraped successfully.",
                }

        failed_count = sum(
            1
            for asin, item in result.items()
            if not asin.startswith("_") and isinstance(item, dict) and not item.get("product_saved")
        )
        pipeline_failed = any(
            stage.get("status") == "failed"
            for stage in (pipeline["analysis"], pipeline["listing_generation"])
        )
        pipeline_errors: list[str] = []
        if pipeline["analysis"].get("status") == "failed":
            pipeline_errors.append(f"analysis: {pipeline['analysis'].get('error')}")
        if pipeline["listing_generation"].get("status") == "failed":
            pipeline_errors.append(f"listing_generation: {pipeline['listing_generation'].get('error')}")
        batch_error = result.get("_batch_error") if isinstance(result, dict) else None
        job_error = " | ".join(item for item in [batch_error, *pipeline_errors] if item) or None
        with SCRAPE_JOBS_LOCK:
            SCRAPE_JOBS[job_id].update(
                {
                    "status": "completed_with_errors" if (failed_count or pipeline_failed) else "completed",
                    "completed_at": utc_now_iso(),
                    "result": {"scrape": result, "pipeline": pipeline},
                    "error": job_error,
                }
            )
            save_scrape_job(SCRAPE_JOBS[job_id])
    except Exception as exc:
        with SCRAPE_JOBS_LOCK:
            SCRAPE_JOBS[job_id].update(
                {
                    "status": "failed",
                    "completed_at": utc_now_iso(),
                    "result": None,
                    "error": str(exc),
                }
            )
            save_scrape_job(SCRAPE_JOBS[job_id])


@app.post("/api/scrape")
def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    normalized_asins = unique_asins_preserve_order(request.asins)
    job_id = str(uuid.uuid4())
    with SCRAPE_JOBS_LOCK:
        SCRAPE_JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "asins": normalized_asins,
            "created_at": utc_now_iso(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        save_scrape_job(SCRAPE_JOBS[job_id])

    background_tasks.add_task(run_scrape_job, job_id, normalized_asins)
    return {"job_id": job_id, "status": "queued", "asins": normalized_asins}


@app.post("/api/scrape-urls")
def start_scrape_from_urls(request: ScrapeUrlsRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        asins = [extract_asin(request.product_url)]
        asins.extend(extract_asin(url) for url in request.competitor_urls)
        asins = unique_asins_preserve_order(asins)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    set_active_asins(asins)
    scrape_request = ScrapeRequest(asins=asins[:10])
    return start_scrape(scrape_request, background_tasks)


@app.get("/api/scrape/{job_id}")
def get_scrape_status(job_id: str) -> dict[str, Any]:
    with SCRAPE_JOBS_LOCK:
        job = SCRAPE_JOBS.get(job_id)
        if job:
            return dict(job)

    persisted_job = load_scrape_job(job_id)
    if not persisted_job:
        raise HTTPException(status_code=404, detail=f"Scrape job {job_id} not found")
    return persisted_job


@app.get("/api/scrape-jobs")
def get_scrape_jobs(limit: int = Query(default=10, ge=1, le=50)) -> list[dict[str, Any]]:
    return latest_scrape_jobs(limit)


@app.post("/api/active-asins")
def set_active_asins_endpoint(request: ActiveAsinsRequest) -> dict[str, Any]:
    normalized_asins = unique_asins_preserve_order(request.asins)
    if not normalized_asins:
        raise HTTPException(status_code=400, detail="No valid ASINs were provided.")
    set_active_asins(normalized_asins)
    return {"active_asins": normalized_asins}
