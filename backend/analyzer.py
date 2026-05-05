#!/usr/bin/env python3
"""Analyze scraped Amazon reviews with Claude and save competitive intelligence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv


load_dotenv(override=True)

DEFAULT_DB_PATH = "backend/data.db"
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
MAX_REVIEW_CHARS_PER_BATCH = 80000
MAX_OUTPUT_TOKENS = 4096
MAX_RETRIES = 4
FALLBACK_MODEL = "claude-sonnet-4-20250514"
DEPRECATED_MODEL_ALIASES = {"claude-3-5-sonnet-latest", "claude-3.5-sonnet-latest"}


BASE_PROMPT = """
You are analyzing Amazon product reviews for competitive intelligence.

Reviews data:
{reviews_data}

Task 1: Identify the top 5 purchase criteria customers care most about.
For each criterion, provide:
- Name of criterion (e.g., "absorption", "taste", "value")
- Why it matters (1 sentence)
- How many reviews mentioned it

Task 2: For each product (ASIN), score it on each criterion (1-10 scale).

Task 3: Extract "customer hooks" - phrases customers use repeatedly (2-5 words).
Examples: "doesn't upset stomach", "easy to swallow", "great value"
For each hook:
- Exact phrase
- Sentiment (positive/negative/neutral)
- Frequency count
- Which ASINs it's associated with

Return as JSON:
{{
  "criteria": [...],
  "product_scores": {{...}},
  "hooks": [...]
}}
""".strip()


FINAL_SYNTHESIS_PROMPT = """
You are combining batch-level Amazon review analyses into one final competitive intelligence report.

Batch analyses:
{batch_analyses}

Create one consolidated JSON response with:
- exactly the top 5 purchase criteria overall
- product_scores for each ASIN on each final criterion, 1-10 scale
- deduplicated customer hooks, merging frequencies and ASIN lists

Return only JSON:
{{
  "criteria": [
    {{"name": "...", "description": "...", "mention_count": 123}}
  ],
  "product_scores": {{
    "ASIN": {{"criterion name": 8}}
  }},
  "hooks": [
    {{"phrase": "...", "sentiment": "positive", "frequency": 12, "asins": ["ASIN"]}}
  ]
}}
""".strip()


def resolve_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return FALLBACK_MODEL
    if normalized in DEPRECATED_MODEL_ALIASES:
        return FALLBACK_MODEL
    return normalized


def ensure_analysis_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            mention_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS product_scores (
            asin TEXT NOT NULL,
            criterion_id INTEGER NOT NULL,
            score REAL,
            PRIMARY KEY (asin, criterion_id),
            FOREIGN KEY (criterion_id) REFERENCES criteria (id)
        );

        CREATE TABLE IF NOT EXISTS hooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL UNIQUE,
            sentiment TEXT,
            frequency INTEGER DEFAULT 0,
            asins TEXT
        );
        """
    )


def load_reviews(db_path: str = DEFAULT_DB_PATH, asins: Optional[list[str]] = None) -> list[dict[str, Any]]:
    filters = ["r.text IS NOT NULL", "TRIM(r.text) != ''"]
    params: list[Any] = []
    if asins:
        placeholders = ",".join("?" for _ in asins)
        filters.append(f"r.asin IN ({placeholders})")
        params.extend(asins)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT r.review_id, r.asin, r.text, r.rating, r.date, p.title
            FROM reviews r
            LEFT JOIN products p ON p.asin = r.asin
            WHERE {' AND '.join(filters)}
            ORDER BY r.asin, r.review_id
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def format_review(review: dict[str, Any], index: int) -> str:
    title = review.get("title") or ""
    return (
        f"Review {index}\n"
        f"ASIN: {review.get('asin')}\n"
        f"Product: {title[:180]}\n"
        f"Rating: {review.get('rating')}\n"
        f"Date: {review.get('date')}\n"
        f"Text: {review.get('text')}\n"
    )


def chunk_reviews(reviews: list[dict[str, Any]], max_chars: int = MAX_REVIEW_CHARS_PER_BATCH) -> list[str]:
    batches: list[str] = []
    current: list[str] = []
    current_chars = 0

    for index, review in enumerate(reviews, start=1):
        formatted = format_review(review, index)
        if current and current_chars + len(formatted) > max_chars:
            batches.append("\n---\n".join(current))
            current = []
            current_chars = 0

        current.append(formatted)
        current_chars += len(formatted)

    if current:
        batches.append("\n---\n".join(current))

    return batches


def call_claude(client: anthropic.Anthropic, prompt: str, model: str) -> str:
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(min(60, 2 ** attempt))

        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = [
                block.text
                for block in response.content
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            ]
            return "\n".join(text_parts).strip()
        except anthropic.RateLimitError as exc:
            last_error = exc
            continue
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
            anthropic.APIStatusError,
        ) as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Claude request failed after retries: {last_error}")


def extract_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Claude response did not contain JSON: {text[:500]}")
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("Claude response JSON must be an object.")
    return payload


def normalize_criterion(raw: dict[str, Any]) -> dict[str, Any]:
    name = raw.get("name") or raw.get("criterion") or raw.get("title")
    description = raw.get("description") or raw.get("why_it_matters") or raw.get("why") or ""
    mention_count = raw.get("mention_count") or raw.get("mentions") or raw.get("count") or 0

    return {
        "name": str(name or "unknown").strip().lower(),
        "description": str(description).strip(),
        "mention_count": int(float(mention_count or 0)),
    }


def normalize_score_value(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("score")
    if value in (None, ""):
        return None
    score = float(value)
    return max(1.0, min(10.0, score))


def normalize_product_scores(raw_scores: Any) -> dict[str, dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {}

    if isinstance(raw_scores, dict):
        for asin, scores in raw_scores.items():
            asin_key = str(asin).upper()
            normalized[asin_key] = {}

            if isinstance(scores, dict):
                for criterion, value in scores.items():
                    score = normalize_score_value(value)
                    if score is not None:
                        normalized[asin_key][str(criterion).strip().lower()] = score
            elif isinstance(scores, list):
                for item in scores:
                    if not isinstance(item, dict):
                        continue
                    criterion = item.get("criterion") or item.get("name")
                    score = normalize_score_value(item.get("score"))
                    if criterion and score is not None:
                        normalized[asin_key][str(criterion).strip().lower()] = score

    elif isinstance(raw_scores, list):
        for item in raw_scores:
            if not isinstance(item, dict):
                continue
            asin = item.get("asin")
            criterion = item.get("criterion") or item.get("name")
            score = normalize_score_value(item.get("score"))
            if asin and criterion and score is not None:
                asin_key = str(asin).upper()
                normalized.setdefault(asin_key, {})[str(criterion).strip().lower()] = score

    return normalized


def normalize_hook(raw: dict[str, Any]) -> dict[str, Any]:
    phrase = raw.get("phrase") or raw.get("hook") or raw.get("text")
    sentiment = str(raw.get("sentiment") or "neutral").lower()
    if sentiment not in {"positive", "negative", "neutral"}:
        sentiment = "neutral"

    frequency = raw.get("frequency") or raw.get("frequency_count") or raw.get("count") or 0
    asins = raw.get("asins") or raw.get("associated_asins") or raw.get("asin") or []
    if isinstance(asins, str):
        asins = [asins]

    return {
        "phrase": str(phrase or "").strip().lower(),
        "sentiment": sentiment,
        "frequency": int(float(frequency or 0)),
        "asins": sorted({str(asin).upper() for asin in asins if asin}),
    }


def normalize_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    criteria = [
        normalize_criterion(item)
        for item in payload.get("criteria", [])
        if isinstance(item, dict)
    ][:5]
    product_scores = normalize_product_scores(payload.get("product_scores", {}))
    hooks = [
        normalize_hook(item)
        for item in payload.get("hooks", [])
        if isinstance(item, dict)
    ]
    hooks = [hook for hook in hooks if hook["phrase"]]

    return {
        "criteria": criteria,
        "product_scores": product_scores,
        "hooks": hooks,
    }


def save_analysis(db_path: str, analysis: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_analysis_tables(conn)
        conn.execute("DELETE FROM product_scores")
        conn.execute("DELETE FROM criteria")
        conn.execute("DELETE FROM hooks")

        criterion_ids: dict[str, int] = {}
        for criterion in analysis["criteria"]:
            cursor = conn.execute(
                """
                INSERT INTO criteria (name, description, mention_count)
                VALUES (?, ?, ?)
                """,
                (criterion["name"], criterion["description"], criterion["mention_count"]),
            )
            criterion_ids[criterion["name"]] = int(cursor.lastrowid)

        for asin, scores in analysis["product_scores"].items():
            for criterion_name, score in scores.items():
                criterion_id = criterion_ids.get(criterion_name)
                if criterion_id is None:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO product_scores (asin, criterion_id, score)
                    VALUES (?, ?, ?)
                    """,
                    (asin, criterion_id, score),
                )

        for hook in analysis["hooks"]:
            conn.execute(
                """
                INSERT INTO hooks (phrase, sentiment, frequency, asins)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phrase) DO UPDATE SET
                    sentiment = excluded.sentiment,
                    frequency = excluded.frequency,
                    asins = excluded.asins
                """,
                (
                    hook["phrase"],
                    hook["sentiment"],
                    hook["frequency"],
                    json.dumps(hook["asins"]),
                ),
            )

        conn.commit()


def analyze_reviews(
    db_path: str = DEFAULT_DB_PATH,
    *,
    model: str = DEFAULT_MODEL,
    max_review_chars_per_batch: int = MAX_REVIEW_CHARS_PER_BATCH,
    asins: Optional[list[str]] = None,
) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY. Add it to .env before running analysis.")

    normalized_asins = [asin.strip().upper() for asin in (asins or []) if asin and asin.strip()]
    reviews = load_reviews(db_path, asins=normalized_asins or None)
    if not reviews:
        raise ValueError("No review text found in the database.")

    client = anthropic.Anthropic(api_key=api_key)
    resolved_model = resolve_model(model)
    batches = chunk_reviews(reviews, max_chars=max_review_chars_per_batch)
    batch_analyses: list[dict[str, Any]] = []

    for batch in batches:
        prompt = BASE_PROMPT.format(reviews_data=batch)
        batch_analyses.append(normalize_analysis(extract_json(call_claude(client, prompt, resolved_model))))

    if len(batch_analyses) == 1:
        final_analysis = batch_analyses[0]
    else:
        prompt = FINAL_SYNTHESIS_PROMPT.format(batch_analyses=json.dumps(batch_analyses, indent=2))
        final_analysis = normalize_analysis(extract_json(call_claude(client, prompt, resolved_model)))

    save_analysis(db_path, final_analysis)
    return {
        "review_count": len(reviews),
        "batch_count": len(batches),
        **final_analysis,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Amazon reviews with Claude.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite database path. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model. Default: {DEFAULT_MODEL}")
    parser.add_argument(
        "--max-review-chars-per-batch",
        type=int,
        default=MAX_REVIEW_CHARS_PER_BATCH,
        help="Approximate review text characters per Claude request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        analysis = analyze_reviews(
            args.db,
            model=args.model,
            max_review_chars_per_batch=args.max_review_chars_per_batch,
        )
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(analysis, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
