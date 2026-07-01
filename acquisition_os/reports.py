"""Daily acquisition reports."""

from __future__ import annotations

from datetime import date
from sqlite3 import Connection, Row

from acquisition_os.db import insert_row, query_rows


def generate_daily_brief(connection: Connection, brief_date: date | None = None) -> str:
    """Create and store a daily brief from current database state."""

    day = brief_date or date.today()
    new_deals = query_rows(
        connection,
        """
        SELECT d.*, c.name AS company_name, c.industry, c.city, c.state
        FROM deals d
        JOIN companies c ON c.id = d.company_id
        WHERE date(d.discovered_at) >= date('now', '-1 day')
        ORDER BY d.discovered_at DESC
        LIMIT 20
        """,
    )
    top_deals = query_rows(
        connection,
        """
        SELECT d.id, d.title, c.name AS company_name, c.city, c.state, d.sde, d.asking_price,
               s.total_score, s.recommendation
        FROM deal_scores s
        JOIN deals d ON d.id = s.deal_id
        JOIN companies c ON c.id = d.company_id
        WHERE s.id IN (SELECT max(id) FROM deal_scores GROUP BY deal_id)
        ORDER BY s.total_score DESC
        LIMIT 20
        """,
    )
    tasks = query_rows(
        connection,
        """
        SELECT t.*, d.title AS deal_title
        FROM tasks t
        LEFT JOIN deals d ON d.id = t.deal_id
        WHERE t.status = 'open' AND (t.due_date IS NULL OR date(t.due_date) <= date('now'))
        ORDER BY t.priority DESC, t.due_date ASC
        LIMIT 20
        """,
    )
    manual_sources = query_rows(
        connection,
        """
        SELECT * FROM source_runs
        WHERE status = 'MANUAL REVIEW REQUIRED'
        ORDER BY started_at DESC
        LIMIT 10
        """,
    )
    news = query_rows(
        connection,
        """
        SELECT * FROM news
        ORDER BY coalesce(published_at, created_at) DESC
        LIMIT 10
        """,
    )
    body = "\n\n".join(
        [
            f"# Acquisition OS Daily Brief - {day.isoformat()}",
            _section("Top 20 Deals", [_deal_line(row) for row in top_deals]),
            _section("New Listings / Targets", [_new_deal_line(row) for row in new_deals]),
            _section("Tasks Due Today", [_task_line(row) for row in tasks]),
            _section("Manual Review Required", [_source_line(row) for row in manual_sources]),
            _section("Transportation / Market News", [_news_line(row) for row in news]),
        ]
    )
    connection.execute("DELETE FROM daily_briefs WHERE brief_date = ?", (day.isoformat(),))
    insert_row(connection, "daily_briefs", {"brief_date": day.isoformat(), "body": body})
    connection.commit()
    return body


def pipeline(connection: Connection) -> str:
    """Summarize current deal count by workflow stage."""

    rows = query_rows(
        connection,
        """
        SELECT stage, count(*) AS count
        FROM deals
        WHERE status = 'active'
        GROUP BY stage
        ORDER BY count DESC, stage ASC
        """,
    )
    return _section("Pipeline", [f"{row['stage']}: {row['count']}" for row in rows])


def tasks(connection: Connection) -> str:
    """Summarize open tasks."""

    rows = query_rows(
        connection,
        """
        SELECT t.*, d.title AS deal_title
        FROM tasks t
        LEFT JOIN deals d ON d.id = t.deal_id
        WHERE t.status = 'open'
        ORDER BY coalesce(t.due_date, '9999-12-31'), t.priority DESC
        LIMIT 50
        """,
    )
    return _section("Open Tasks", [_task_line(row) for row in rows])


def _section(title: str, lines: list[str]) -> str:
    if not lines:
        return f"## {title}\nNo items."
    return "## " + title + "\n" + "\n".join(f"- {line}" for line in lines)


def _deal_line(row: Row) -> str:
    price = _fmt_money(row["asking_price"])
    sde = _fmt_money(row["sde"])
    return f"{row['total_score']}/100 {row['recommendation']} - #{row['id']} {row['title']} ({sde} SDE, {price} price)"


def _new_deal_line(row: Row) -> str:
    place = ", ".join(part for part in (row["city"], row["state"]) if part)
    place = f" - {place}" if place else ""
    return f"#{row['id']} {row['title']}{place}"


def _task_line(row: Row) -> str:
    deal = f" [{row['deal_title']}]" if "deal_title" in row.keys() and row["deal_title"] else ""
    due = row["due_date"] or "no due date"
    return f"P{row['priority']} {due}{deal}: {row['title']}"


def _source_line(row: Row) -> str:
    notes = f" - {row['notes']}" if row["notes"] else ""
    return f"{row['source_name']}{notes}"


def _news_line(row: Row) -> str:
    source = f" ({row['source']})" if row["source"] else ""
    return f"{row['title']}{source}"


def _fmt_money(value: object) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "unknown"
