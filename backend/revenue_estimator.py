#!/usr/bin/env python3
"""Estimate Amazon monthly revenue from Best Seller Rank and price."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any, Optional


DEFAULT_DB_PATH = "backend/data.db"


def parse_bsr(bsr: Any) -> Optional[int]:
    if bsr in (None, ""):
        return None
    if isinstance(bsr, int):
        return bsr
    if isinstance(bsr, float):
        return int(bsr)

    numbers = re.findall(r"\d[\d,]*", str(bsr))
    if not numbers:
        return None

    return int(numbers[-1].replace(",", ""))


def estimate_units_per_month(bsr: int) -> int:
    if bsr <= 10:
        return 8000
    if bsr <= 50:
        return 4000
    if bsr <= 100:
        return 2000
    if bsr <= 500:
        return 500
    if bsr <= 1000:
        return 200
    if bsr <= 5000:
        return 50
    return 10


def confidence_for_bsr(bsr: int) -> str:
    if bsr < 100:
        return "high"
    if bsr < 1000:
        return "medium"
    return "low"


def estimate_revenue(bsr: Any, price: Any) -> dict[str, Any]:
    parsed_bsr = parse_bsr(bsr)
    parsed_price = float(price) if price not in (None, "") else None

    if parsed_bsr is None or parsed_price is None:
        return {
            "estimated_units_per_month": 0,
            "estimated_revenue_per_month": 0.0,
            "confidence": "low",
        }

    units = estimate_units_per_month(parsed_bsr)
    return {
        "estimated_units_per_month": units,
        "estimated_revenue_per_month": round(units * parsed_price, 2),
        "confidence": confidence_for_bsr(parsed_bsr),
    }


def ensure_revenue_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(products)").fetchall()
    }
    migrations = {
        "estimated_units_per_month": "ALTER TABLE products ADD COLUMN estimated_units_per_month INTEGER",
        "estimated_revenue_per_month": "ALTER TABLE products ADD COLUMN estimated_revenue_per_month REAL",
        "revenue_confidence": "ALTER TABLE products ADD COLUMN revenue_confidence TEXT",
    }

    for column, statement in migrations.items():
        if column not in existing_columns:
            conn.execute(statement)


def estimate_all_products(db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_revenue_columns(conn)

        rows = conn.execute(
            """
            SELECT asin, title, price, bsr
            FROM products
            ORDER BY asin
            """
        ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            estimate = estimate_revenue(row["bsr"], row["price"])
            conn.execute(
                """
                UPDATE products
                SET estimated_units_per_month = ?,
                    estimated_revenue_per_month = ?,
                    revenue_confidence = ?
                WHERE asin = ?
                """,
                (
                    estimate["estimated_units_per_month"],
                    estimate["estimated_revenue_per_month"],
                    estimate["confidence"],
                    row["asin"],
                ),
            )
            results.append(
                {
                    "asin": row["asin"],
                    "title": row["title"],
                    "price": row["price"],
                    "bsr": row["bsr"],
                    **estimate,
                }
            )

        conn.commit()
        return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate revenue for scraped Amazon products.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite database path. Default: {DEFAULT_DB_PATH}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(estimate_all_products(args.db), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
