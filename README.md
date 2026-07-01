# Acquisition OS

Local command-line operating system for finding, evaluating, financing, and managing a small business acquisition.

The first build is intentionally simple:

- Python standard library only
- SQLite database
- Command-line workflow
- Modular collectors for compliant sources
- Rule-based 100 point deal scoring
- SBA acquisition model
- Outreach drafts, task tracking, pipeline, and daily brief

## Quick Start

```bash
python3 -m acquisition_os.cli init
python3 -m acquisition_os.cli import-csv examples/sample_deals.csv --source "manual import"
python3 -m acquisition_os.cli score-deals
python3 -m acquisition_os.cli pipeline
python3 -m acquisition_os.cli generate-brief
python3 -m acquisition_os.cli model-deal 1 --down-payment 125000 --interest-rate 0.11 --save
python3 -m acquisition_os.cli generate-outreach 1 --save
```

The default database lives at `data/acquisition_os.sqlite3`.

## Core Commands

```bash
python3 -m acquisition_os.cli run-daily
python3 -m acquisition_os.cli run-search --provider rss --url "https://example.com/feed.xml" --source "transportation news"
python3 -m acquisition_os.cli run-search --provider saved-html --path saved-alert.html --source "broker alert"
python3 -m acquisition_os.cli run-search --provider serpapi --query "Georgia logistics business for sale"
python3 -m acquisition_os.cli run-search --provider manual --source "BizBuySell" --query "Review saved listings manually"
python3 -m acquisition_os.cli import-csv path/to/listings.csv
python3 -m acquisition_os.cli add-task "Call broker" --deal-id 1 --due-date 2026-07-02 --priority 3
python3 -m acquisition_os.cli stage 1 "NDA Requested"
python3 -m acquisition_os.cli news --add-title "SBA rates changed" --source "lender" --summary "Update model assumptions"
```

## CSV Import Columns

The importer accepts common aliases. Useful columns include:

- `company_name`
- `title`
- `industry`
- `city`
- `state`
- `description`
- `asking_price`
- `revenue`
- `sde`
- `ebitda`
- `inventory`
- `customer_concentration`
- `source_url`
- `source_name`

## Compliant Sourcing

This system does not scrape restricted marketplaces, bypass logins, bypass robots.txt, or bypass CAPTCHAs.

Supported first-build inputs:

- CSV imports
- Saved HTML files
- RSS feeds
- Google Programmable Search API
- Bing Search API
- SerpAPI
- Manual review logs for restricted sources

Set these optional environment variables for API collectors:

```bash
export SERPAPI_KEY="..."
export BING_SEARCH_KEY="..."
export GOOGLE_CSE_KEY="..."
export GOOGLE_CSE_ID="..."
```

## OpenAI Enrichment

`acquisition_os/ai.py` contains an optional OpenAI helper that returns JSON-only enrichment for raw source results. It is not automatically run yet, because the first priority is a reliable local core. Set `OPENAI_API_KEY` before using it in a future enrichment command.

## Deal Score

The 100 point score follows the acquisition mandate:

- Cash Flow: 25
- Asset Quality: 20
- Offshore Opportunity: 15
- SBA Likelihood: 15
- Customer Risk: 10
- Geography: 5
- Growth Opportunity: 10

Scores are transparent and stored in `deal_scores`.

## Test

```bash
python3 -m unittest discover -s tests
```
