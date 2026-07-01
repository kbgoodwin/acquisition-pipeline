"""CSV and saved-result import helpers."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from sqlite3 import Connection

from acquisition_os.db import upsert_company


FIELD_ALIASES = {
    "name": "company_name",
    "company": "company_name",
    "business": "company_name",
    "business_name": "company_name",
    "title": "title",
    "listing_title": "title",
    "industry": "industry",
    "website": "website",
    "city": "city",
    "state": "state",
    "region": "region",
    "description": "description",
    "summary": "description",
    "asking_price": "asking_price",
    "price": "asking_price",
    "purchase_price": "asking_price",
    "revenue": "revenue",
    "sales": "revenue",
    "cash_flow": "sde",
    "sde": "sde",
    "ebitda": "ebitda",
    "inventory": "inventory",
    "customer_concentration": "customer_concentration",
    "source_url": "source_url",
    "url": "source_url",
    "source_name": "source_name",
    "source": "source_name",
    "listed_at": "listed_at",
}


def import_csv(connection: Connection, csv_path: Path, source_name: str | None = None) -> int:
    """Import business listings from a flexible CSV file."""

    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for raw_row in reader:
            row = _normalize_row(raw_row)
            company_name = row.get("company_name") or row.get("title")
            if not company_name:
                continue
            company_id = upsert_company(
                connection,
                {
                    "name": company_name,
                    "industry": row.get("industry"),
                    "website": row.get("website"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "region": row.get("region"),
                    "description": row.get("description"),
                    "source": source_name or row.get("source_name") or csv_path.name,
                },
            )
            deal = {
                "company_id": company_id,
                "title": row.get("title") or company_name,
                "asking_price": _money(row.get("asking_price")),
                "revenue": _money(row.get("revenue")),
                "sde": _money(row.get("sde")),
                "ebitda": _money(row.get("ebitda")),
                "inventory": _money(row.get("inventory")),
                "customer_concentration": _percent(row.get("customer_concentration")),
                "source_url": row.get("source_url"),
                "source_name": source_name or row.get("source_name") or csv_path.name,
                "listed_at": row.get("listed_at"),
            }
            inserted = _insert_deal_ignore_duplicate(connection, deal)
            count += inserted
    connection.commit()
    return count


def _insert_deal_ignore_duplicate(connection: Connection, values: dict[str, object]) -> int:
    keys = list(values.keys())
    placeholders = ", ".join("?" for _ in keys)
    columns = ", ".join(keys)
    cursor = connection.execute(
        f"INSERT OR IGNORE INTO deals ({columns}) VALUES ({placeholders})",
        [values[key] for key in keys],
    )
    return int(cursor.rowcount > 0)


def _normalize_row(raw_row: dict[str, str | None]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in raw_row.items():
        canonical = FIELD_ALIASES.get(_slug(key), _slug(key))
        normalized[canonical] = (value or "").strip()
    return normalized


def _slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _money(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.]", "", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _percent(value: str | None) -> float | None:
    if not value:
        return None
    number = _money(value)
    if number is None:
        return None
    return number / 100 if number > 1 else number
