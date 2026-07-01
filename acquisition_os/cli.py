"""Command-line interface for Acquisition OS."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from sqlite3 import Connection, Row

from acquisition_os.collectors import log_manual_review, run_rss, run_saved_html, run_search_api
from acquisition_os.config import DEFAULT_SETTINGS, WORKFLOW_STAGES
from acquisition_os.db import connect, init_db, insert_row, query_rows
from acquisition_os.finance import FinancingInputs, model_financing, sensitivity
from acquisition_os.importers import import_csv
from acquisition_os.outreach import broker_questions, diligence_checklist, owner_outreach
from acquisition_os.reports import generate_daily_brief, pipeline as pipeline_report, tasks as tasks_report
from acquisition_os.scoring import DealScore, score_deal


JOINED_DEAL_SQL = """
SELECT d.*, c.name AS company_name, c.industry, c.website, c.city, c.state, c.region, c.description
FROM deals d
JOIN companies c ON c.id = d.company_id
"""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    init_db(args.db)
    with connect(args.db) as connection:
        return int(args.handler(connection, args) or 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acq",
        description="Local acquisition operating system for sourcing, scoring, modeling, and outreach.",
    )
    parser.add_argument("--db", default=str(DEFAULT_SETTINGS.database_path), help="SQLite database path")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Create the SQLite database")
    init.set_defaults(handler=cmd_init)

    import_cmd = sub.add_parser("import-csv", help="Import business listings from CSV")
    import_cmd.add_argument("path")
    import_cmd.add_argument("--source")
    import_cmd.set_defaults(handler=cmd_import_csv)

    search = sub.add_parser("run-search", help="Run a compliant source collector")
    search.add_argument("--provider", choices=["rss", "saved-html", "serpapi", "bing", "google_cse", "manual"], required=True)
    search.add_argument("--query", help="Search query for API providers")
    search.add_argument("--url", help="RSS feed URL")
    search.add_argument("--path", help="Saved HTML path")
    search.add_argument("--source", default="source")
    search.set_defaults(handler=cmd_run_search)

    daily = sub.add_parser("run-daily", help="Run the core daily workflow")
    daily.set_defaults(handler=cmd_run_daily)

    score = sub.add_parser("score-deals", help="Score active deals")
    score.add_argument("--deal-id", type=int)
    score.set_defaults(handler=cmd_score_deals)

    brief = sub.add_parser("generate-brief", help="Generate today's daily brief")
    brief.add_argument("--output", help="Optional markdown output path")
    brief.set_defaults(handler=cmd_generate_brief)

    model = sub.add_parser("model-deal", help="Model SBA financing for a deal")
    model.add_argument("deal_id", type=int)
    model.add_argument("--purchase-price", type=float)
    model.add_argument("--sde", type=float)
    model.add_argument("--down-payment", type=float, default=125_000)
    model.add_argument("--interest-rate", type=float, default=0.11)
    model.add_argument("--term-years", type=int, default=10)
    model.add_argument("--seller-note", type=float, default=0)
    model.add_argument("--working-capital", type=float, default=0)
    model.add_argument("--save", action="store_true")
    model.add_argument("--sensitivity", action="store_true")
    model.set_defaults(handler=cmd_model_deal)

    outreach = sub.add_parser("generate-outreach", help="Generate owner outreach, broker questions, and diligence checklist")
    outreach.add_argument("deal_id", type=int)
    outreach.add_argument("--save", action="store_true")
    outreach.set_defaults(handler=cmd_generate_outreach)

    pipeline = sub.add_parser("pipeline", help="Show pipeline by stage")
    pipeline.set_defaults(handler=cmd_pipeline)

    tasks = sub.add_parser("tasks", help="Show open tasks")
    tasks.set_defaults(handler=cmd_tasks)

    add_task = sub.add_parser("add-task", help="Add a task")
    add_task.add_argument("title")
    add_task.add_argument("--deal-id", type=int)
    add_task.add_argument("--due-date")
    add_task.add_argument("--priority", type=int, default=2)
    add_task.add_argument("--notes")
    add_task.set_defaults(handler=cmd_add_task)

    stage = sub.add_parser("stage", help="Move a deal to a workflow stage")
    stage.add_argument("deal_id", type=int)
    stage.add_argument("stage", choices=WORKFLOW_STAGES)
    stage.set_defaults(handler=cmd_stage)

    news = sub.add_parser("news", help="Add or list acquisition-relevant news")
    news.add_argument("--add-title")
    news.add_argument("--url")
    news.add_argument("--source")
    news.add_argument("--summary")
    news.add_argument("--relevance")
    news.add_argument("--published-at")
    news.set_defaults(handler=cmd_news)

    return parser


def cmd_init(connection: Connection, args: argparse.Namespace) -> int:
    print(f"Acquisition OS database ready: {args.db}")
    return 0


def cmd_import_csv(connection: Connection, args: argparse.Namespace) -> int:
    count = import_csv(connection, Path(args.path), args.source)
    print(f"Imported {count} businesses.")
    return 0


def cmd_run_search(connection: Connection, args: argparse.Namespace) -> int:
    if args.provider == "rss":
        if not args.url:
            raise SystemExit("--url is required for RSS")
        count = run_rss(connection, args.url, args.source)
    elif args.provider == "saved-html":
        if not args.path:
            raise SystemExit("--path is required for saved HTML")
        count = run_saved_html(connection, Path(args.path), args.source)
    elif args.provider == "manual":
        count = log_manual_review(connection, args.source, args.query or "Manual source review requested")
    else:
        if not args.query:
            raise SystemExit("--query is required for API search providers")
        count = run_search_api(connection, args.query, args.provider)
    print(f"Source run complete. New raw results: {count}")
    return 0


def cmd_run_daily(connection: Connection, args: argparse.Namespace) -> int:
    scored = _score_deals(connection, None)
    brief = generate_daily_brief(connection)
    print(f"Scored {scored} deals.\n")
    print(brief)
    return 0


def cmd_score_deals(connection: Connection, args: argparse.Namespace) -> int:
    count = _score_deals(connection, args.deal_id)
    print(f"Scored {count} deals.")
    return 0


def cmd_generate_brief(connection: Connection, args: argparse.Namespace) -> int:
    body = generate_daily_brief(connection)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"Brief written to {output}")
    else:
        print(body)
    return 0


def cmd_model_deal(connection: Connection, args: argparse.Namespace) -> int:
    row = _get_deal(connection, args.deal_id)
    purchase_price = args.purchase_price if args.purchase_price is not None else row["asking_price"]
    sde = args.sde if args.sde is not None else row["sde"]
    if not purchase_price or not sde:
        raise SystemExit("Deal needs purchase price and SDE, or pass --purchase-price and --sde.")
    inputs = FinancingInputs(
        purchase_price=float(purchase_price),
        sde=float(sde),
        down_payment=args.down_payment,
        interest_rate=args.interest_rate,
        term_years=args.term_years,
        seller_note=args.seller_note,
        working_capital=args.working_capital,
    )
    result = model_financing(inputs)
    if args.save:
        insert_row(
            connection,
            "financial_models",
            {
                "deal_id": args.deal_id,
                "purchase_price": result.purchase_price,
                "down_payment": result.down_payment,
                "sba_loan": result.sba_loan,
                "seller_note": result.seller_note,
                "interest_rate": result.interest_rate,
                "term_years": result.term_years,
                "monthly_payment": result.monthly_payment,
                "annual_debt_service": result.annual_debt_service,
                "dscr": result.dscr,
                "cash_on_cash": result.cash_on_cash,
                "post_debt_owner_income": result.post_debt_owner_income,
                "breakeven_sde": result.breakeven_sde,
                "working_capital": result.working_capital,
                "maximum_offer": result.maximum_offer,
                "roi": result.roi,
                "assumptions_json": json.dumps(result.assumptions),
            },
        )
        connection.commit()
    print(json.dumps(asdict(result), indent=2))
    if args.sensitivity:
        print("\nSensitivity:")
        print(json.dumps([asdict(item) for item in sensitivity(inputs)], indent=2))
    return 0


def cmd_generate_outreach(connection: Connection, args: argparse.Namespace) -> int:
    row = _get_deal(connection, args.deal_id)
    owner = owner_outreach(row)
    broker = broker_questions(row)
    diligence = diligence_checklist(row)
    body = "\n\n".join([owner, broker, diligence])
    if args.save:
        insert_row(
            connection,
            "outreach",
            {
                "deal_id": args.deal_id,
                "channel": "email",
                "direction": "outbound",
                "subject": f"Confidential conversation about {row['company_name']}",
                "body": owner,
                "status": "draft",
            },
        )
        insert_row(
            connection,
            "notes",
            {
                "deal_id": args.deal_id,
                "company_id": row["company_id"],
                "body": broker + "\n\n" + diligence,
            },
        )
        connection.commit()
    print(body)
    return 0


def cmd_pipeline(connection: Connection, args: argparse.Namespace) -> int:
    print(pipeline_report(connection))
    return 0


def cmd_tasks(connection: Connection, args: argparse.Namespace) -> int:
    print(tasks_report(connection))
    return 0


def cmd_add_task(connection: Connection, args: argparse.Namespace) -> int:
    task_id = insert_row(
        connection,
        "tasks",
        {
            "deal_id": args.deal_id,
            "title": args.title,
            "due_date": args.due_date,
            "priority": args.priority,
            "notes": args.notes,
        },
    )
    connection.commit()
    print(f"Task #{task_id} added.")
    return 0


def cmd_stage(connection: Connection, args: argparse.Namespace) -> int:
    connection.execute(
        "UPDATE deals SET stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (args.stage, args.deal_id),
    )
    connection.commit()
    print(f"Deal #{args.deal_id} moved to {args.stage}.")
    return 0


def cmd_news(connection: Connection, args: argparse.Namespace) -> int:
    if args.add_title:
        news_id = insert_row(
            connection,
            "news",
            {
                "title": args.add_title,
                "url": args.url,
                "source": args.source,
                "summary": args.summary,
                "relevance": args.relevance,
                "published_at": args.published_at,
            },
        )
        connection.commit()
        print(f"News #{news_id} added.")
        return 0
    rows = query_rows(connection, "SELECT * FROM news ORDER BY coalesce(published_at, created_at) DESC LIMIT 25")
    for row in rows:
        print(f"#{row['id']} {row['title']} ({row['source'] or 'unknown source'})")
    if not rows:
        print("No news yet.")
    return 0


def _score_deals(connection: Connection, deal_id: int | None) -> int:
    where = " WHERE d.id = ?" if deal_id else " WHERE d.status = 'active'"
    params = (deal_id,) if deal_id else ()
    rows = query_rows(connection, JOINED_DEAL_SQL + where, params)
    for row in rows:
        score = score_deal(row)
        _save_score(connection, row["id"], score)
    connection.commit()
    return len(rows)


def _save_score(connection: Connection, deal_id: int, score: DealScore) -> None:
    insert_row(
        connection,
        "deal_scores",
        {
            "deal_id": deal_id,
            "total_score": score.total_score,
            "cash_flow_score": score.cash_flow_score,
            "asset_quality_score": score.asset_quality_score,
            "offshore_score": score.offshore_score,
            "sba_score": score.sba_score,
            "customer_risk_score": score.customer_risk_score,
            "geography_score": score.geography_score,
            "growth_score": score.growth_score,
            "recommendation": score.recommendation,
            "risks": score.risks,
            "rationale": score.rationale,
        },
    )


def _get_deal(connection: Connection, deal_id: int) -> Row:
    rows = query_rows(connection, JOINED_DEAL_SQL + " WHERE d.id = ?", (deal_id,))
    if not rows:
        raise SystemExit(f"Deal #{deal_id} not found")
    return rows[0]


if __name__ == "__main__":
    sys.exit(main())
