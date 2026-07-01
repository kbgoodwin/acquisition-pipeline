"""Optional OpenAI enrichment.

The system works without this module. When OPENAI_API_KEY is set, this helper
can enrich raw search results while keeping the response contract JSON-only.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


SYSTEM_PROMPT = """
You extract and evaluate acquisition targets for a private internal buyer.
Return JSON only with these keys:
company_name, title, industry, city, state, asking_price, revenue, sde,
customer_concentration, summary, acquisition_quality, offshore_opportunity,
sba_likelihood, risks, owner_outreach, broker_questions, diligence_checklist.
Use null when unknown.
"""


def enrich_result(title: str, url: str, snippet: str, model: str = "gpt-4.1-mini") -> dict[str, Any]:
    """Call OpenAI Responses API using only the standard library."""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"title": title, "url": url, "snippet": snippet}),
            },
        ],
        "text": {"format": {"type": "json_object"}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    text = _extract_text(data)
    return json.loads(text)


def _extract_text(response: dict[str, Any]) -> str:
    if "output_text" in response:
        return str(response["output_text"])
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                return str(content.get("text", ""))
    raise RuntimeError("OpenAI response did not include output text")
