#!/usr/bin/env python3
"""Generate optimized Amazon listings from scraped data and review analysis."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv


load_dotenv(override=True)

DEFAULT_DB_PATH = "backend/data.db"
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_OUTPUT_TOKENS = 4096
MAX_RETRIES = 4
FALLBACK_MODEL = "claude-sonnet-4-20250514"
DEPRECATED_MODEL_ALIASES = {"claude-3-5-sonnet-latest", "claude-3.5-sonnet-latest"}


PROMPT_TEMPLATE = """
You are an Amazon listing optimization expert.

Product to optimize: {current_title}
Current bullets: {current_bullets}

Competitive intelligence:
- Top 5 customer purchase criteria: {criteria}
- Gaps: {gaps}
- Customer hooks to use: {top_hooks}
- Winning patterns from competitors: {winning_patterns}

Generate:
1. New title (200 chars max, includes these keywords: {top_keywords})
   - Must mention top 2 customer criteria
   - Use power words from customer hooks

2. Five bullet points (each 100-150 chars)
   - Bullet 1: Address #1 customer concern
   - Bullet 2: Address #2 customer concern
   - Bullet 3: Differentiation vs competitors
   - Bullet 4: Social proof (use customer language)
   - Bullet 5: Guarantee/reassurance

3. Product description (3 paragraphs, ~300 words)
   - Paragraph 1: Problem + solution
   - Paragraph 2: Benefits (address all 5 criteria)
   - Paragraph 3: Why choose us + CTA

Use natural customer language. Reference specific hooks: {top_hooks}

Return as JSON:
{{
  "title": "...",
  "bullets": ["...", "...", "...", "...", "..."],
  "description": "..."
}}
""".strip()


STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "you",
    "are",
    "but",
    "not",
    "have",
    "has",
    "was",
    "were",
    "our",
    "its",
    "into",
    "per",
    "count",
    "tablet",
    "tablets",
    "supplement",
    "supplements",
}


def resolve_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return FALLBACK_MODEL
    if normalized in DEPRECATED_MODEL_ALIASES:
        return FALLBACK_MODEL
    return normalized


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> Optional[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def load_product(conn: sqlite3.Connection, asin: str) -> dict[str, Any]:
    product = fetch_one(
        conn,
        """
        SELECT asin, title, price, rating, review_count, bsr,
               estimated_units_per_month, estimated_revenue_per_month
        FROM products
        WHERE asin = ?
        """,
        (asin,),
    )
    if not product:
        raise ValueError(f"No product found for ASIN {asin}.")
    return product


def load_competitors(conn: sqlite3.Connection, current_asin: str, competitor_asins: list[str]) -> list[dict[str, Any]]:
    if competitor_asins:
        placeholders = ",".join("?" for _ in competitor_asins)
        rows = conn.execute(
            f"""
            SELECT asin, title, price, rating, review_count, bsr,
                   estimated_units_per_month, estimated_revenue_per_month
            FROM products
            WHERE asin IN ({placeholders})
            ORDER BY estimated_revenue_per_month DESC NULLS LAST, review_count DESC NULLS LAST
            """,
            competitor_asins,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT asin, title, price, rating, review_count, bsr,
                   estimated_units_per_month, estimated_revenue_per_month
            FROM products
            WHERE asin != ? AND title IS NOT NULL
            ORDER BY estimated_revenue_per_month DESC NULLS LAST, review_count DESC NULLS LAST
            LIMIT 9
            """,
            (current_asin,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_criteria(conn: sqlite3.Connection, asins: Optional[list[str]] = None) -> list[dict[str, Any]]:
    if asins:
        placeholders = ",".join("?" for _ in asins)
        rows = conn.execute(
            f"""
            SELECT DISTINCT c.id, c.name, c.description, c.mention_count
            FROM criteria c
            JOIN product_scores ps ON ps.criterion_id = c.id
            WHERE ps.asin IN ({placeholders})
            ORDER BY c.mention_count DESC, c.id
            LIMIT 5
            """,
            asins,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, name, description, mention_count
            FROM criteria
            ORDER BY mention_count DESC, id
            LIMIT 5
            """
        ).fetchall()
    return [dict(row) for row in rows]


def load_hooks(conn: sqlite3.Connection, limit: int = 10, asins: Optional[list[str]] = None) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT phrase, sentiment, frequency, asins
        FROM hooks
        ORDER BY CASE WHEN sentiment = 'positive' THEN 0 ELSE 1 END, frequency DESC, phrase
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    hooks: list[dict[str, Any]] = []
    asin_set = set(asins or [])
    for row in rows:
        item = dict(row)
        try:
            item["asins"] = json.loads(item.get("asins") or "[]")
        except json.JSONDecodeError:
            item["asins"] = []
        if asin_set and not (asin_set & set(item["asins"])):
            continue
        hooks.append(item)
        if len(hooks) >= limit:
            break
    return hooks


def words(text: str) -> list[str]:
    return [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text)
        if word.lower() not in STOPWORDS
    ]


def top_keywords(product: dict[str, Any], competitors: list[dict[str, Any]], criteria: list[dict[str, Any]], hooks: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    for source in [product, *competitors]:
        counter.update(words(source.get("title") or ""))
    for criterion in criteria:
        counter.update(words(criterion.get("name") or ""))
    for hook in hooks:
        counter.update(words(hook.get("phrase") or ""))

    return [keyword for keyword, _ in counter.most_common(12)]


def find_gaps(product: dict[str, Any], competitors: list[dict[str, Any]], criteria: list[dict[str, Any]], hooks: list[dict[str, Any]]) -> list[str]:
    product_text = (product.get("title") or "").lower()
    gaps: list[str] = []

    for criterion in criteria:
        name = str(criterion.get("name") or "").replace("_", " ")
        if name and name not in product_text:
            gaps.append(f"Current title does not clearly claim {name}.")

    competitor_text = " ".join(comp.get("title") or "" for comp in competitors).lower()
    for hook in hooks:
        phrase = str(hook.get("phrase") or "")
        if phrase and phrase not in product_text and any(word in competitor_text for word in words(phrase)):
            gaps.append(f"Competitors/reviews emphasize '{phrase}' more clearly.")

    if not gaps:
        gaps.append("No clear gap found from the current stored title; use criteria and hooks to sharpen positioning.")

    return gaps[:8]


def winning_patterns(competitors: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    for competitor in competitors[:3]:
        title = competitor.get("title") or ""
        if not title:
            continue
        patterns.append(
            f"{competitor['asin']}: title leads with brand/product form and includes benefit keywords; "
            f"price={competitor.get('price')}, rating={competitor.get('rating')}, reviews={competitor.get('review_count')}"
        )
    return patterns or ["No competitor title patterns available from scraped rows."]


def call_claude(prompt: str, model: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY. Add it to .env before generating a listing.")

    client = anthropic.Anthropic(api_key=api_key)
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
        raise ValueError("Generated listing JSON must be an object.")
    return payload


def clean_listing(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    bullets = payload.get("bullets") or []
    description = str(payload.get("description") or "").strip()

    if not isinstance(bullets, list):
        raise ValueError("Generated listing must include bullets as a list.")

    cleaned_bullets = [str(bullet).strip() for bullet in bullets if str(bullet).strip()][:5]
    if len(cleaned_bullets) != 5:
        raise ValueError("Generated listing must include exactly 5 bullet points.")
    if not title or not description:
        raise ValueError("Generated listing must include title and description.")

    return {
        "title": title[:200],
        "bullets": cleaned_bullets,
        "description": description,
    }


def save_generated_listing(
    conn: sqlite3.Connection,
    asin: str,
    listing: dict[str, Any],
    *,
    model: str,
    input_snapshot: dict[str, Any],
) -> int:
    ensure_generated_listing_table(conn)
    cursor = conn.execute(
        """
        INSERT INTO generated_listings (asin, title, bullets, description, model, generated_at, input_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asin,
            listing["title"],
            json.dumps(listing["bullets"]),
            listing["description"],
            model,
            utc_now_iso(),
            json.dumps(input_snapshot),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def build_prompt_context(conn: sqlite3.Connection, asin: str, competitor_asins: list[str]) -> dict[str, Any]:
    product = load_product(conn, asin)
    competitors = load_competitors(conn, asin, competitor_asins)
    tracked_asins = [asin, *[item["asin"] for item in competitors]]
    criteria = load_criteria(conn, asins=tracked_asins)
    hooks = load_hooks(conn, limit=10, asins=tracked_asins)
    keywords = top_keywords(product, competitors, criteria, hooks)
    gaps = find_gaps(product, competitors, criteria, hooks)
    patterns = winning_patterns(competitors)

    return {
        "product": product,
        "competitors": competitors,
        "criteria": criteria,
        "hooks": hooks,
        "top_keywords": keywords,
        "gaps": gaps,
        "winning_patterns": patterns,
    }


def generate_listing(
    asin: str,
    *,
    competitor_asins: Optional[list[str]] = None,
    db_path: str = DEFAULT_DB_PATH,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    normalized_asin = asin.strip().upper()
    competitor_asins = [item.strip().upper() for item in (competitor_asins or []) if item.strip()]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        context = build_prompt_context(conn, normalized_asin, competitor_asins)

        prompt = PROMPT_TEMPLATE.format(
            current_title=context["product"].get("title") or f"ASIN {normalized_asin}",
            current_bullets=json.dumps([], indent=2),
            criteria=json.dumps(context["criteria"], indent=2),
            gaps=json.dumps(context["gaps"], indent=2),
            top_hooks=json.dumps(context["hooks"], indent=2),
            winning_patterns=json.dumps(context["winning_patterns"], indent=2),
            top_keywords=", ".join(context["top_keywords"]),
        )
        resolved_model = resolve_model(model)
        listing = clean_listing(extract_json(call_claude(prompt, resolved_model)))
        listing_id = save_generated_listing(
            conn,
            normalized_asin,
            listing,
            model=resolved_model,
            input_snapshot=context,
        )

    return {
        "id": listing_id,
        "asin": normalized_asin,
        **listing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an optimized Amazon listing with Claude.")
    parser.add_argument("asin", help="Current product ASIN to optimize.")
    parser.add_argument("--competitors", nargs="*", default=[], help="Optional competitor ASINs.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite database path. Default: {DEFAULT_DB_PATH}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model. Default: {DEFAULT_MODEL}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        listing = generate_listing(
            args.asin,
            competitor_asins=args.competitors,
            db_path=args.db,
            model=args.model,
        )
    except Exception as exc:
        print(f"Listing generation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(listing, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
