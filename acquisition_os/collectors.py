"""Compliant sourcing collectors.

Network-backed collectors only call sources that are intended for programmatic
or public access. Restricted marketplaces and login/CAPTCHA sources are logged
as manual review items instead of scraped.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from sqlite3 import Connection

from acquisition_os.db import insert_row


MANUAL_REVIEW_SOURCES = {
    "bizbuysell",
    "bizquest",
    "businessesforsale",
    "dealstream",
    "loopnet",
    "crexi",
    "transworld",
    "murphy business",
    "sunbelt",
    "vr business brokers",
    "empire flippers",
    "acquire.com",
    "axial",
}


@dataclass(frozen=True)
class SearchResult:
    source_name: str
    title: str
    url: str
    snippet: str
    raw: dict[str, object]


class LinkExtractor(HTMLParser):
    """Small parser for saved HTML alert pages."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attr_map = dict(attrs)
            self._current_href = attr_map.get("href")
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            text = " ".join(part.strip() for part in self._current_text if part.strip())
            if text:
                self.links.append((text, self._current_href))
            self._current_href = None
            self._current_text = []


def run_rss(connection: Connection, feed_url: str, source_name: str = "rss") -> int:
    """Fetch a public RSS feed and store entries as raw search results."""

    run_id = _start_run(connection, source_name, "rss")
    results = _read_rss(feed_url, source_name)
    count = _store_results(connection, run_id, results)
    _finish_run(connection, run_id, "complete", count)
    connection.commit()
    return count


def run_saved_html(connection: Connection, path: Path, source_name: str = "saved_html") -> int:
    """Parse links from a saved HTML file without crawling the source website."""

    run_id = _start_run(connection, source_name, "saved_html")
    parser = LinkExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    results = [
        SearchResult(
            source_name=source_name,
            title=title,
            url=url,
            snippet=f"Saved HTML link from {path.name}",
            raw={"path": str(path), "title": title, "url": url},
        )
        for title, url in parser.links
    ]
    count = _store_results(connection, run_id, results)
    _finish_run(connection, run_id, "complete", count)
    connection.commit()
    return count


def run_search_api(connection: Connection, query: str, provider: str) -> int:
    """Run an API-backed search when credentials are configured."""

    provider = provider.lower()
    if _requires_manual_review(provider):
        return log_manual_review(connection, provider, f"Restricted source requested for query: {query}")
    run_id = _start_run(connection, provider, "search_api")
    if provider == "serpapi":
        results = _serpapi(query)
    elif provider == "bing":
        results = _bing(query)
    elif provider == "google_cse":
        results = _google_cse(query)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    count = _store_results(connection, run_id, results)
    _finish_run(connection, run_id, "complete", count)
    connection.commit()
    return count


def log_manual_review(connection: Connection, source_name: str, notes: str) -> int:
    """Record that a source needs manual review instead of automated scraping."""

    run_id = _start_run(connection, source_name, "manual_review")
    _finish_run(connection, run_id, "MANUAL REVIEW REQUIRED", 0, notes)
    connection.commit()
    return 0


def _read_rss(feed_url: str, source_name: str) -> list[SearchResult]:
    with urllib.request.urlopen(feed_url, timeout=30) as response:
        content = response.read()
    root = ET.fromstring(content)
    items = root.findall(".//item")
    results: list[SearchResult] = []
    for item in items:
        title = item.findtext("title") or "Untitled"
        link = item.findtext("link") or ""
        description = item.findtext("description") or ""
        results.append(
            SearchResult(
                source_name=source_name,
                title=title,
                url=link,
                snippet=description,
                raw={"title": title, "url": link, "description": description},
            )
        )
    return results


def _serpapi(query: str) -> list[SearchResult]:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        raise RuntimeError("SERPAPI_KEY is not set")
    params = urllib.parse.urlencode({"engine": "google", "q": query, "api_key": key})
    data = _json_get(f"https://serpapi.com/search.json?{params}")
    return [
        SearchResult(
            source_name="serpapi",
            title=str(item.get("title", "")),
            url=str(item.get("link", "")),
            snippet=str(item.get("snippet", "")),
            raw=dict(item),
        )
        for item in data.get("organic_results", [])
    ]


def _bing(query: str) -> list[SearchResult]:
    key = os.environ.get("BING_SEARCH_KEY")
    if not key:
        raise RuntimeError("BING_SEARCH_KEY is not set")
    url = "https://api.bing.microsoft.com/v7.0/search?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": key})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [
        SearchResult(
            source_name="bing",
            title=str(item.get("name", "")),
            url=str(item.get("url", "")),
            snippet=str(item.get("snippet", "")),
            raw=dict(item),
        )
        for item in data.get("webPages", {}).get("value", [])
    ]


def _google_cse(query: str) -> list[SearchResult]:
    key = os.environ.get("GOOGLE_CSE_KEY")
    cx = os.environ.get("GOOGLE_CSE_ID")
    if not key or not cx:
        raise RuntimeError("GOOGLE_CSE_KEY and GOOGLE_CSE_ID must be set")
    params = urllib.parse.urlencode({"key": key, "cx": cx, "q": query})
    data = _json_get(f"https://www.googleapis.com/customsearch/v1?{params}")
    return [
        SearchResult(
            source_name="google_cse",
            title=str(item.get("title", "")),
            url=str(item.get("link", "")),
            snippet=str(item.get("snippet", "")),
            raw=dict(item),
        )
        for item in data.get("items", [])
    ]


def _json_get(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _store_results(connection: Connection, run_id: int, results: list[SearchResult]) -> int:
    count = 0
    for result in results:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO raw_search_results
            (source_run_id, source_name, title, url, snippet, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                result.source_name,
                result.title,
                result.url,
                result.snippet,
                json.dumps(result.raw),
            ),
        )
        count += int(cursor.rowcount > 0)
    return count


def _start_run(connection: Connection, source_name: str, source_type: str) -> int:
    return insert_row(
        connection,
        "source_runs",
        {"source_name": source_name, "source_type": source_type, "status": "running"},
    )


def _finish_run(
    connection: Connection,
    run_id: int,
    status: str,
    results_found: int,
    notes: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE source_runs
        SET status = ?, results_found = ?, notes = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, results_found, notes, run_id),
    )


def _requires_manual_review(source_name: str) -> bool:
    lowered = source_name.lower()
    return any(source in lowered for source in MANUAL_REVIEW_SOURCES)
