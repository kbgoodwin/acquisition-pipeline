"""SQLite persistence layer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        industry TEXT,
        website TEXT,
        city TEXT,
        state TEXT,
        region TEXT,
        description TEXT,
        source TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, city, state)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY,
        company_id INTEGER REFERENCES companies(id),
        title TEXT NOT NULL,
        asking_price REAL,
        revenue REAL,
        sde REAL,
        ebitda REAL,
        inventory REAL,
        real_estate_included INTEGER DEFAULT 0,
        customer_concentration REAL,
        stage TEXT NOT NULL DEFAULT 'Prospect',
        status TEXT NOT NULL DEFAULT 'active',
        source_url TEXT,
        source_name TEXT,
        listed_at TEXT,
        discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(title, source_url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owners (
        id INTEGER PRIMARY KEY,
        company_id INTEGER REFERENCES companies(id),
        name TEXT,
        title TEXT,
        email TEXT,
        phone TEXT,
        linkedin_url TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        company_id INTEGER REFERENCES companies(id),
        name TEXT,
        role TEXT,
        email TEXT,
        phone TEXT,
        source TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS brokers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        firm TEXT,
        email TEXT,
        phone TEXT,
        website TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, firm)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lenders (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        bank TEXT,
        email TEXT,
        phone TEXT,
        sba_preferred INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, bank)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        title TEXT NOT NULL,
        due_date TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        priority INTEGER NOT NULL DEFAULT 2,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outreach (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        contact_id INTEGER REFERENCES contacts(id),
        channel TEXT NOT NULL,
        direction TEXT NOT NULL DEFAULT 'outbound',
        subject TEXT,
        body TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        sent_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS financial_models (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        purchase_price REAL NOT NULL,
        down_payment REAL NOT NULL,
        sba_loan REAL NOT NULL,
        seller_note REAL NOT NULL DEFAULT 0,
        interest_rate REAL NOT NULL,
        term_years INTEGER NOT NULL,
        monthly_payment REAL NOT NULL,
        annual_debt_service REAL NOT NULL,
        dscr REAL,
        cash_on_cash REAL,
        post_debt_owner_income REAL,
        breakeven_sde REAL,
        working_capital REAL,
        maximum_offer REAL,
        roi REAL,
        assumptions_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        name TEXT NOT NULL,
        path TEXT,
        document_type TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        company_id INTEGER REFERENCES companies(id),
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS valuations (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER REFERENCES deals(id),
        method TEXT NOT NULL,
        low_value REAL,
        high_value REAL,
        target_value REAL,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT,
        source TEXT,
        summary TEXT,
        relevance TEXT,
        published_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(title, url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_briefs (
        id INTEGER PRIMARY KEY,
        brief_date TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(brief_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_runs (
        id INTEGER PRIMARY KEY,
        source_name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        results_found INTEGER NOT NULL DEFAULT 0,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_search_results (
        id INTEGER PRIMARY KEY,
        source_run_id INTEGER REFERENCES source_runs(id),
        source_name TEXT NOT NULL,
        title TEXT,
        url TEXT,
        snippet TEXT,
        raw_json TEXT,
        extracted_json TEXT,
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_name, url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS duplicate_groups (
        id INTEGER PRIMARY KEY,
        canonical_deal_id INTEGER REFERENCES deals(id),
        reason TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS duplicate_group_members (
        id INTEGER PRIMARY KEY,
        duplicate_group_id INTEGER REFERENCES duplicate_groups(id),
        deal_id INTEGER REFERENCES deals(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(duplicate_group_id, deal_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deal_scores (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER NOT NULL REFERENCES deals(id),
        total_score INTEGER NOT NULL,
        cash_flow_score INTEGER NOT NULL,
        asset_quality_score INTEGER NOT NULL,
        offshore_score INTEGER NOT NULL,
        sba_score INTEGER NOT NULL,
        customer_risk_score INTEGER NOT NULL,
        geography_score INTEGER NOT NULL,
        growth_score INTEGER NOT NULL,
        recommendation TEXT NOT NULL,
        risks TEXT NOT NULL,
        rationale TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries enabled."""

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path: str | Path) -> None:
    """Create every table used by the acquisition system."""

    with connect(path) as connection:
        for statement in SCHEMA:
            connection.execute(statement)


def insert_row(connection: sqlite3.Connection, table: str, values: Mapping[str, Any]) -> int:
    """Insert one row and return its id."""

    keys = list(values.keys())
    placeholders = ", ".join("?" for _ in keys)
    columns = ", ".join(keys)
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    cursor = connection.execute(sql, [values[key] for key in keys])
    return int(cursor.lastrowid)


def upsert_company(connection: sqlite3.Connection, values: Mapping[str, Any]) -> int:
    """Insert a company or return the existing id for the same name/location."""

    existing = connection.execute(
        """
        SELECT id FROM companies
        WHERE lower(name) = lower(?)
          AND coalesce(lower(city), '') = coalesce(lower(?), '')
          AND coalesce(lower(state), '') = coalesce(lower(?), '')
        """,
        (values.get("name"), values.get("city"), values.get("state")),
    ).fetchone()
    if existing:
        return int(existing["id"])
    return insert_row(connection, "companies", values)


def query_rows(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[Any] | None = None,
) -> list[sqlite3.Row]:
    """Return all rows for a query."""

    return list(connection.execute(sql, parameters or ()))


def bulk_insert(
    connection: sqlite3.Connection,
    table: str,
    rows: Iterable[Mapping[str, Any]],
) -> int:
    """Insert many rows, returning the number attempted."""

    count = 0
    for row in rows:
        insert_row(connection, table, row)
        count += 1
    return count
