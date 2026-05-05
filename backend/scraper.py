#!/usr/bin/env python3
"""Bright Data Amazon scraper entrypoint.

Usage:
    BRIGHT_DATA_API_KEY=... python backend/scraper.py B0CHHSFMRL
    BRIGHT_DATA_API_KEY=... python backend/scraper.py MAINASIN --competitors ASIN1 ASIN2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv


load_dotenv(override=True)

BRIGHT_DATA_TRIGGER_URL = "https://api.brightdata.com/datasets/v3/trigger"
BRIGHT_DATA_SCRAPE_URL = "https://api.brightdata.com/datasets/v3/scrape"
BRIGHT_DATA_PROGRESS_URL = "https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
BRIGHT_DATA_SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

AMAZON_PRODUCT_DATASET_ID = os.getenv("BRIGHT_DATA_AMAZON_PRODUCT_DATASET_ID", "gd_l7q7dkf244hwjntr0")
AMAZON_REVIEWS_DATASET_ID = os.getenv("BRIGHT_DATA_AMAZON_REVIEWS_DATASET_ID", "gd_le8e811kzy4ggddlq")
AMAZON_QA_DATASET_ID = os.getenv("BRIGHT_DATA_AMAZON_QA_DATASET_ID")

DEFAULT_DB_PATH = "backend/data.db"
DEFAULT_DOMAIN = "amazon.com"
DEFAULT_ZIPCODE = os.getenv("BRIGHT_DATA_AMAZON_ZIPCODE", "")
DEFAULT_LANGUAGE = os.getenv("BRIGHT_DATA_AMAZON_LANGUAGE", "")
MAX_BATCH_SIZE = 10
REQUEST_TIMEOUT_SECONDS = 180
POLL_INTERVAL_SECONDS = 10
MAX_POLL_SECONDS = 600
RATE_LIMIT_SECONDS = 2
PRODUCT_DATA_KEYS = {
    "title",
    "product_title",
    "name",
    "price",
    "final_price",
    "buybox_price",
    "rating",
    "stars",
    "review_count",
    "reviews_count",
    "ratings_count",
    "bsr",
    "bs_rank",
    "root_bs_rank",
    "best_seller_rank",
    "best_sellers_rank",
    "main_image",
    "images",
    "image_urls",
}
REVIEW_DATA_KEYS = {"text", "review_text", "body", "content", "review", "rating", "stars", "date", "review_date"}


class BrightDataError(RuntimeError):
    pass


def normalize_asin(asin: str) -> str:
    cleaned = asin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", cleaned):
        raise ValueError(f"Invalid ASIN: {asin!r}. Expected 10 letters/numbers.")
    return cleaned


def amazon_product_url(asin: str, domain: str = DEFAULT_DOMAIN) -> str:
    return f"https://www.{domain}/dp/{asin}"


def amazon_product_url_variants(asin: str, domain: str = DEFAULT_DOMAIN) -> list[str]:
    return [
        f"https://www.{domain}/dp/{asin}",
        f"https://www.{domain}/-/dp/{asin}",
        f"https://www.{domain}/gp/product/{asin}",
    ]


def amazon_review_url_variants(asin: str, domain: str = DEFAULT_DOMAIN) -> list[str]:
    return [
        f"https://www.{domain}/product-reviews/{asin}",
        f"https://www.{domain}/product-reviews/{asin}?reviewerType=all_reviews",
        f"https://www.{domain}/product-reviews/{asin}?sortBy=recent",
    ]


def build_input(url: str, *, zipcode: str = "", language: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"url": url}
    if zipcode:
        payload["zipcode"] = zipcode
    if language:
        payload["language"] = language
    return payload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                asin TEXT PRIMARY KEY,
                title TEXT,
                price REAL,
                rating REAL,
                review_count INTEGER,
                bsr TEXT,
                scraped_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                asin TEXT NOT NULL,
                text TEXT,
                rating REAL,
                date TEXT,
                FOREIGN KEY (asin) REFERENCES products (asin)
            );

            CREATE TABLE IF NOT EXISTS images (
                image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                url TEXT NOT NULL,
                position INTEGER NOT NULL,
                UNIQUE (asin, url),
                FOREIGN KEY (asin) REFERENCES products (asin)
            );

            CREATE TABLE IF NOT EXISTS qna (
                question_id TEXT PRIMARY KEY,
                asin TEXT NOT NULL,
                question TEXT,
                answer TEXT,
                position INTEGER NOT NULL,
                FOREIGN KEY (asin) REFERENCES products (asin)
            );
            """
        )


class BrightDataClient:
    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
        rate_limit_seconds: int = RATE_LIMIT_SECONDS,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries
        self.client = httpx.Client(
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                backoff = min(60, (2**attempt) * self.rate_limit_seconds)
                time.sleep(backoff)

            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = int(retry_after) if retry_after and retry_after.isdigit() else 30
                    time.sleep(delay)
                    continue
                if 500 <= response.status_code < 600:
                    last_error = BrightDataError(f"Bright Data {response.status_code}: {response.text[:500]}")
                    continue

                if 400 <= response.status_code < 500:
                    raise BrightDataError(f"Bright Data {response.status_code}: {response.text[:1000]}")

                time.sleep(self.rate_limit_seconds)
                return response
            except (httpx.HTTPError, BrightDataError) as exc:
                last_error = exc

        raise BrightDataError(f"Bright Data request failed after retries: {last_error}")

    def trigger(self, dataset_id: str, inputs: list[dict[str, Any]]) -> str:
        query = urlencode({"dataset_id": dataset_id, "format": "json"})
        response = self._request("POST", f"{BRIGHT_DATA_TRIGGER_URL}?{query}", json={"input": inputs})
        payload = response.json()
        snapshot_id = payload.get("snapshot_id")
        if not snapshot_id:
            raise BrightDataError(f"Missing snapshot_id in trigger response: {payload}")
        return snapshot_id

    def scrape_realtime(self, dataset_id: str, inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        query = urlencode(
            {
                "dataset_id": dataset_id,
                "format": "json",
                "notify": "false",
                "include_errors": "true",
            }
        )
        response = self._request("POST", f"{BRIGHT_DATA_SCRAPE_URL}?{query}", json={"input": inputs})
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("results") or payload.get("records")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return [payload]
        raise BrightDataError(f"Unexpected scrape payload type: {type(payload).__name__}")

    def wait_for_snapshot(self, snapshot_id: str, max_wait_seconds: int = MAX_POLL_SECONDS) -> None:
        deadline = time.time() + max_wait_seconds
        last_status = "unknown"

        while time.time() < deadline:
            response = self._request("GET", BRIGHT_DATA_PROGRESS_URL.format(snapshot_id=snapshot_id))
            payload = response.json()
            last_status = str(payload.get("status", "")).lower()

            if last_status == "ready":
                return
            if last_status == "failed":
                raise BrightDataError(f"Snapshot {snapshot_id} failed: {payload}")

            time.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"Snapshot {snapshot_id} was not ready after {max_wait_seconds}s. Last status: {last_status}")

    def download_snapshot(self, snapshot_id: str) -> list[dict[str, Any]]:
        query = urlencode({"format": "json"})
        response = self._request("GET", f"{BRIGHT_DATA_SNAPSHOT_URL.format(snapshot_id=snapshot_id)}?{query}")
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("results") or payload.get("records")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return [payload]
        raise BrightDataError(f"Unexpected snapshot payload type: {type(payload).__name__}")

    def collect(self, dataset_id: str, inputs: list[dict[str, Any]], *, realtime: bool = True) -> list[dict[str, Any]]:
        if realtime:
            return self.scrape_realtime(dataset_id, inputs)

        snapshot_id = self.trigger(dataset_id, inputs)
        self.wait_for_snapshot(snapshot_id)
        return self.download_snapshot(snapshot_id)


def first_value(record: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", []):
            return value
    return None


def has_any_data(record: dict[str, Any], keys: set[str]) -> bool:
    return any(record.get(key) not in (None, "", []) for key in keys)


def record_error(record: dict[str, Any]) -> Optional[str]:
    error = first_value(record, ["error", "errors", "error_message", "message", "status_message"])
    if error:
        return str(error)
    return None


def record_error_code(record: dict[str, Any]) -> Optional[str]:
    error_code = first_value(record, ["error_code", "code", "status_code"])
    return str(error_code) if error_code else None


def records_indicate_in_progress(records: list[dict[str, Any]]) -> bool:
    if not records:
        return False
    for record in records:
        error = (record_error(record) or "").lower()
        if "still in progress" in error or "monitor snapshot endpoint" in error:
            return True
    return False


def valid_product_record(record: dict[str, Any]) -> bool:
    return has_any_data(record, PRODUCT_DATA_KEYS) and not record_error(record)


def valid_review_record(record: dict[str, Any]) -> bool:
    return has_any_data(record, REVIEW_DATA_KEYS) and not record_error(record)


def to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else None


def extract_images(record: dict[str, Any]) -> list[str]:
    images: list[str] = []
    raw_images = first_value(record, ["images", "image_urls", "product_images", "photos"])
    main_image = first_value(record, ["main_image", "image", "thumbnail"])

    if isinstance(main_image, str):
        images.append(main_image)

    if isinstance(raw_images, list):
        for item in raw_images:
            if isinstance(item, str):
                images.append(item)
            elif isinstance(item, dict):
                url = first_value(item, ["url", "image", "large", "hi_res", "src"])
                if isinstance(url, str):
                    images.append(url)
    elif isinstance(raw_images, str):
        images.append(raw_images)

    seen: set[str] = set()
    deduped: list[str] = []
    for url in images:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def extract_bsr(record: dict[str, Any]) -> Optional[str]:
    bsr = first_value(
        record,
        [
            "bsr",
            "bs_rank",
            "root_bs_rank",
            "best_seller_rank",
            "best_sellers_rank",
            "best_seller_ranking",
            "sales_rank",
            "product_rank",
        ],
    )
    if bsr is None:
        return None
    if isinstance(bsr, (dict, list)):
        return json.dumps(bsr, ensure_ascii=True)
    return str(bsr)


def extract_questions(record: dict[str, Any], limit: int = 10) -> list[dict[str, Optional[str]]]:
    direct_question = first_value(record, ["question", "q", "question_text"])
    direct_answer = first_value(record, ["answer", "a", "answer_text", "top_answer"])
    if direct_question or direct_answer:
        return [
            {
                "question": str(direct_question) if direct_question is not None else None,
                "answer": str(direct_answer) if direct_answer is not None else None,
            }
        ]

    raw_questions = first_value(record, ["qna", "qa", "questions", "customer_questions", "questions_and_answers"])
    if not isinstance(raw_questions, list):
        return []

    questions: list[dict[str, Optional[str]]] = []
    for item in raw_questions[:limit]:
        if isinstance(item, str):
            questions.append({"question": item, "answer": None})
        elif isinstance(item, dict):
            question = first_value(item, ["question", "q", "title", "text"])
            answer = first_value(item, ["answer", "a", "top_answer", "answer_text"])
            questions.append(
                {
                    "question": str(question) if question is not None else None,
                    "answer": str(answer) if answer is not None else None,
                }
            )
    return questions


def stable_review_id(asin: str, record: dict[str, Any]) -> str:
    existing_id = first_value(record, ["review_id", "id", "reviewer_id"])
    if existing_id:
        return f"{asin}:{existing_id}"

    fingerprint = "|".join(
        str(first_value(record, keys) or "")
        for keys in (["text", "review_text", "body", "content"], ["rating", "stars"], ["date", "review_date"])
    )
    digest = hashlib.sha1(f"{asin}|{fingerprint}".encode("utf-8")).hexdigest()
    return f"{asin}:{digest}"


def asin_from_url(url: str) -> Optional[str]:
    match = re.search(r"/(?:dp|gp/product|product-reviews)/([A-Z0-9]{10})(?:[/?#]|$)", url, flags=re.IGNORECASE)
    return match.group(1) if match else None


def asin_from_record(record: dict[str, Any]) -> Optional[str]:
    direct_asin = first_value(record, ["asin", "product_asin", "parent_asin"])
    if direct_asin and re.fullmatch(r"[A-Z0-9]{10}", str(direct_asin).upper()):
        return str(direct_asin).upper()

    input_payload = record.get("input")
    if isinstance(input_payload, dict):
        input_asin = first_value(input_payload, ["asin", "product_asin"])
        if input_asin and re.fullmatch(r"[A-Z0-9]{10}", str(input_asin).upper()):
            return str(input_asin).upper()

        input_url = input_payload.get("url")
        if isinstance(input_url, str):
            return asin_from_url(input_url)

    url = record.get("url")
    if isinstance(url, str):
        return asin_from_url(url)

    return None


def save_product(conn: sqlite3.Connection, asin: str, record: dict[str, Any], scraped_at: str) -> None:
    conn.execute(
        """
        INSERT INTO products (asin, title, price, rating, review_count, bsr, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asin) DO UPDATE SET
            title = excluded.title,
            price = excluded.price,
            rating = excluded.rating,
            review_count = excluded.review_count,
            bsr = excluded.bsr,
            scraped_at = excluded.scraped_at
        """,
        (
            asin,
            first_value(record, ["title", "product_title", "name"]),
            to_float(first_value(record, ["price", "final_price", "buybox_price", "list_price"])),
            to_float(first_value(record, ["rating", "stars", "average_rating"])),
            to_int(first_value(record, ["review_count", "reviews_count", "ratings_count", "total_reviews"])),
            extract_bsr(record),
            scraped_at,
        ),
    )


def save_images(conn: sqlite3.Connection, asin: str, image_urls: list[str]) -> None:
    for position, url in enumerate(image_urls, start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO images (asin, url, position)
            VALUES (?, ?, ?)
            """,
            (asin, url, position),
        )


def save_reviews(conn: sqlite3.Connection, asin: str, records: list[dict[str, Any]], limit: int = 100) -> None:
    for record in records[:limit]:
        review_id = stable_review_id(asin, record)
        conn.execute(
            """
            INSERT INTO reviews (review_id, asin, text, rating, date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(review_id) DO UPDATE SET
                text = excluded.text,
                rating = excluded.rating,
                date = excluded.date
            """,
            (
                review_id,
                asin,
                first_value(record, ["text", "review_text", "body", "content", "review"]),
                to_float(first_value(record, ["rating", "stars", "review_rating"])),
                first_value(record, ["date", "review_date", "created_at"]),
            ),
        )


def save_qna(conn: sqlite3.Connection, asin: str, questions: list[dict[str, Optional[str]]]) -> None:
    for position, item in enumerate(questions[:10], start=1):
        question = item.get("question")
        answer = item.get("answer")
        digest = hashlib.sha1(f"{asin}|{position}|{question}|{answer}".encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO qna (question_id, asin, question, answer, position)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                question = excluded.question,
                answer = excluded.answer,
                position = excluded.position
            """,
            (f"{asin}:{digest}", asin, question, answer, position),
        )


def group_by_asin(records: list[dict[str, Any]], requested_asins: list[str]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {asin: [] for asin in requested_asins}
    for index, record in enumerate(records):
        record_asin = asin_from_record(record)
        if record_asin in grouped:
            grouped[record_asin].append(record)
        elif index < len(requested_asins):
            grouped[requested_asins[index]].append(record)
    return grouped


def retry_empty_asins(
    client: BrightDataClient,
    dataset_id: str,
    asins: list[str],
    grouped_records: dict[str, list[dict[str, Any]]],
    *,
    domain: str,
    zipcode: str,
    language: str,
    validator: Any,
    realtime: bool,
    url_variant_builder: Any,
) -> dict[str, list[dict[str, Any]]]:
    empty_asins = [
        asin
        for asin in asins
        if not any(validator(record) for record in grouped_records.get(asin, []))
    ]
    if not empty_asins:
        return grouped_records

    for url_index, _ in enumerate(url_variant_builder(empty_asins[0], domain)):
        remaining_asins = [
            asin
            for asin in empty_asins
            if not any(validator(record) for record in grouped_records.get(asin, []))
        ]
        if not remaining_asins:
            break

        retry_inputs = [
            build_input(url_variant_builder(asin, domain)[url_index], zipcode=zipcode, language=language)
            for asin in remaining_asins
        ]
        retry_records = client.collect(dataset_id, retry_inputs, realtime=realtime)
        retry_grouped = group_by_asin(retry_records, remaining_asins)
        for asin, records in retry_grouped.items():
            grouped_records[asin] = [*grouped_records.get(asin, []), *records]
    return grouped_records


def scrape_asins(
    asins: list[str],
    *,
    api_key: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    domain: str = DEFAULT_DOMAIN,
    zipcode: str = DEFAULT_ZIPCODE,
    language: str = DEFAULT_LANGUAGE,
    review_limit: int = 100,
    realtime: bool = True,
    include_products: bool = True,
    include_reviews: bool = True,
) -> dict[str, Any]:
    normalized_asins = [normalize_asin(asin) for asin in asins]
    if len(normalized_asins) > MAX_BATCH_SIZE:
        raise ValueError(f"Expected at most {MAX_BATCH_SIZE} ASINs per run.")

    token = api_key or os.getenv("BRIGHT_DATA_API_KEY")
    if not token:
        raise ValueError("Missing BRIGHT_DATA_API_KEY. Add it to .env or pass api_key.")

    init_db(db_path)
    product_inputs = [build_input(amazon_product_url(asin, domain), zipcode=zipcode, language=language) for asin in normalized_asins]
    review_inputs = [build_input(amazon_review_url_variants(asin, domain)[0], zipcode=zipcode, language=language) for asin in normalized_asins]
    scraped_at = utc_now_iso()
    client = BrightDataClient(token)
    reviews_realtime = bool(os.getenv("BRIGHT_DATA_REVIEWS_REALTIME", "").strip().lower() in {"1", "true", "yes"})

    try:
        product_records = client.collect(AMAZON_PRODUCT_DATASET_ID, product_inputs, realtime=realtime) if include_products else []
        review_records = client.collect(AMAZON_REVIEWS_DATASET_ID, review_inputs, realtime=reviews_realtime) if include_reviews else []
        if include_reviews and reviews_realtime and records_indicate_in_progress(review_records):
            review_records = client.collect(AMAZON_REVIEWS_DATASET_ID, review_inputs, realtime=False)
        qa_records = client.collect(AMAZON_QA_DATASET_ID, product_inputs, realtime=realtime) if AMAZON_QA_DATASET_ID else []

        products_by_asin = group_by_asin(product_records, normalized_asins)
        reviews_by_asin = group_by_asin(review_records, normalized_asins)
        if include_products:
            products_by_asin = retry_empty_asins(
                client,
                AMAZON_PRODUCT_DATASET_ID,
                normalized_asins,
                products_by_asin,
                domain=domain,
                zipcode=zipcode,
                language=language,
                validator=valid_product_record,
                realtime=realtime,
                url_variant_builder=amazon_product_url_variants,
            )
        if include_reviews:
            reviews_by_asin = retry_empty_asins(
                client,
                AMAZON_REVIEWS_DATASET_ID,
                normalized_asins,
                reviews_by_asin,
                domain=domain,
                zipcode=zipcode,
                language=language,
                validator=valid_review_record,
                realtime=realtime,
                url_variant_builder=amazon_review_url_variants,
            )
    finally:
        client.close()

    qa_by_asin = group_by_asin(qa_records, normalized_asins)

    summary: dict[str, Any] = {}
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for asin in normalized_asins:
            product_candidates = products_by_asin.get(asin, [])
            product_record = next((record for record in product_candidates if valid_product_record(record)), None)
            review_batch = [record for record in reviews_by_asin.get(asin, []) if valid_review_record(record)][:review_limit]
            review_candidates = reviews_by_asin.get(asin, [])

            qna_items = extract_questions(product_record or {}, limit=10)
            for qa_record in qa_by_asin.get(asin, []):
                qna_items.extend(extract_questions(qa_record, limit=10))
            qna_items = qna_items[:10]

            images = extract_images(product_record or {})
            if product_record:
                save_product(conn, asin, product_record, scraped_at)
                save_images(conn, asin, images)
                save_qna(conn, asin, qna_items)
            elif include_reviews and review_batch:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO products (asin, scraped_at)
                    VALUES (?, ?)
                    """,
                    (asin, scraped_at),
                )

            if review_batch:
                save_reviews(conn, asin, review_batch, limit=review_limit)

            raw_product_error = record_error(product_candidates[0]) if product_candidates else None
            raw_product_error_code = record_error_code(product_candidates[0]) if product_candidates else None
            raw_review_error = record_error(review_candidates[0]) if review_candidates else None
            raw_review_error_code = record_error_code(review_candidates[0]) if review_candidates else None

            summary[asin] = {
                "product_saved": bool(product_record),
                "product_error": raw_product_error,
                "product_error_code": raw_product_error_code,
                "product_records_returned": len(product_candidates),
                "reviews_error": raw_review_error,
                "reviews_error_code": raw_review_error_code,
                "review_records_returned": len(review_candidates),
                "reviews_saved": len(review_batch),
                "images_saved": len(images),
                "qna_saved": len(qna_items),
            }

        conn.commit()

    return summary


def scrape_asins_resilient(asins: list[str], **kwargs: Any) -> dict[str, Any]:
    try:
        return scrape_asins(asins, **kwargs)
    except Exception as batch_error:
        summary: dict[str, Any] = {
            "_batch_error": str(batch_error),
        }
        for asin in asins:
            try:
                summary.update(scrape_asins([asin], **kwargs))
            except Exception as asin_error:
                summary[normalize_asin(asin)] = {
                    "product_saved": False,
                    "product_error": str(asin_error),
                    "product_error_code": "request_failed",
                    "product_records_returned": 0,
                    "reviews_saved": 0,
                    "images_saved": 0,
                    "qna_saved": 0,
                }
        return summary


def scrape_main_and_competitors(main_asin: str, competitor_asins: list[str], **kwargs: Any) -> dict[str, Any]:
    return scrape_asins([main_asin, *competitor_asins[:9]], **kwargs)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Amazon product data with Bright Data and save it to SQLite.")
    parser.add_argument("asin", help="Main Amazon product ASIN.")
    parser.add_argument("--competitors", nargs="*", default=[], help="Up to 9 competitor ASINs.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite database path. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help=f"Amazon domain. Default: {DEFAULT_DOMAIN}")
    parser.add_argument("--zipcode", default=DEFAULT_ZIPCODE, help="Optional Amazon delivery zipcode for Bright Data.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Optional Amazon language code for Bright Data.")
    parser.add_argument("--review-limit", type=int, default=100, help="Number of reviews to save per ASIN.")
    parser.add_argument("--async-mode", action="store_true", help="Use Bright Data trigger/progress/snapshot flow.")
    parser.add_argument("--skip-products", action="store_true", help="Skip product detail scraping.")
    parser.add_argument("--skip-reviews", action="store_true", help="Skip review scraping.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        summary = scrape_main_and_competitors(
            args.asin,
            args.competitors,
            db_path=args.db,
            domain=args.domain,
            zipcode=args.zipcode,
            language=args.language,
            review_limit=args.review_limit,
            realtime=not args.async_mode,
            include_products=not args.skip_products,
            include_reviews=not args.skip_reviews,
        )
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
