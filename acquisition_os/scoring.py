"""Rule-based deal scoring for the acquisition mandate."""

from __future__ import annotations

from dataclasses import dataclass
from sqlite3 import Row

from acquisition_os.config import Criteria, DEFAULT_CRITERIA


@dataclass(frozen=True)
class DealScore:
    total_score: int
    cash_flow_score: int
    asset_quality_score: int
    offshore_score: int
    sba_score: int
    customer_risk_score: int
    geography_score: int
    growth_score: int
    recommendation: str
    risks: str
    rationale: str


def score_deal(row: Row, criteria: Criteria = DEFAULT_CRITERIA) -> DealScore:
    """Score one joined deal/company row using a transparent 100 point model."""

    text = _text(row)
    sde = _number(row["sde"])
    price = _number(row["asking_price"])
    revenue = _number(row["revenue"])
    concentration = _number(row["customer_concentration"])

    cash_flow = _cash_flow_score(sde, price, criteria)
    asset_quality = _keyword_score(
        text,
        criteria.highest_priority_industries,
        criteria.second_priority_industries,
        criteria.avoid_industries,
        20,
    )
    offshore = _offshore_score(text)
    sba = _sba_score(sde, price, revenue, text, criteria)
    customer_risk = _customer_risk_score(concentration, criteria)
    geography = _geography_score(text, criteria)
    growth = _growth_score(text)
    total = cash_flow + asset_quality + offshore + sba + customer_risk + geography + growth
    risks = _risks(row, concentration, criteria)
    recommendation = _recommendation(total, risks)
    rationale = (
        f"Score {total}/100. Cash flow {cash_flow}/25, assets {asset_quality}/20, "
        f"offshore {offshore}/15, SBA {sba}/15, customer risk {customer_risk}/10, "
        f"geo {geography}/5, growth {growth}/10."
    )
    return DealScore(
        total_score=total,
        cash_flow_score=cash_flow,
        asset_quality_score=asset_quality,
        offshore_score=offshore,
        sba_score=sba,
        customer_risk_score=customer_risk,
        geography_score=geography,
        growth_score=growth,
        recommendation=recommendation,
        risks=risks,
        rationale=rationale,
    )


def _cash_flow_score(sde: float | None, price: float | None, criteria: Criteria) -> int:
    if not sde:
        return 8
    score = 0
    if criteria.target_sde_min <= sde <= criteria.target_sde_max:
        score += 17
    elif 200_000 <= sde < criteria.target_sde_min or criteria.target_sde_max < sde <= 800_000:
        score += 12
    else:
        score += 5
    if price and criteria.price_min <= price <= criteria.price_max:
        score += 5
    elif price:
        score += 2
    if price and price / sde <= 4.0:
        score += 3
    elif price and price / sde <= 5.0:
        score += 1
    return min(score, 25)


def _keyword_score(
    text: str,
    high: tuple[str, ...],
    second: tuple[str, ...],
    avoid: tuple[str, ...],
    maximum: int,
) -> int:
    if any(term in text for term in avoid):
        return 2
    if any(term in text for term in high):
        return maximum
    if any(term in text for term in second):
        return max(round(maximum * 0.65), 1)
    if "ups store" in text:
        if "fresno" in text or "porterville" in text:
            return round(maximum * 0.45)
        return 1
    return round(maximum * 0.35)


def _offshore_score(text: str) -> int:
    strong = ("admin", "dispatch", "back office", "customer service", "quoting", "billing", "scheduling")
    moderate = ("operations", "route", "recurring", "service", "maintenance")
    score = 4
    if any(term in text for term in strong):
        score += 7
    if any(term in text for term in moderate):
        score += 4
    return min(score, 15)


def _sba_score(
    sde: float | None,
    price: float | None,
    revenue: float | None,
    text: str,
    criteria: Criteria,
) -> int:
    score = 4
    if sde and criteria.target_sde_min <= sde <= criteria.target_sde_max:
        score += 4
    if price and criteria.price_min <= price <= criteria.price_max:
        score += 3
    if revenue and sde and 0.08 <= sde / revenue <= 0.35:
        score += 2
    if "real estate" not in text and "franchise requiring owner" not in text:
        score += 1
    if "seller financing" in text or "seller note" in text or "sba" in text:
        score += 1
    return min(score, 15)


def _customer_risk_score(concentration: float | None, criteria: Criteria) -> int:
    if concentration is None:
        return 6
    if concentration <= criteria.max_customer_concentration:
        return 10
    if concentration <= 0.45:
        return 5
    return 1


def _geography_score(text: str, criteria: Criteria) -> int:
    if any(place in text for place in criteria.primary_geographies):
        return 5
    if any(place in text for place in criteria.secondary_geographies):
        return 4
    if any(place in text for place in criteria.third_geographies):
        return 3
    return 1


def _growth_score(text: str) -> int:
    terms = ("growth", "expand", "capacity", "recurring", "contracts", "fragmented", "under-marketed")
    score = 3 + sum(1 for term in terms if term in text)
    return min(score, 10)


def _risks(row: Row, concentration: float | None, criteria: Criteria) -> str:
    risks: list[str] = []
    text = _text(row)
    if any(term in text for term in criteria.avoid_industries):
        risks.append("Avoid-list industry signal")
    if concentration and concentration > criteria.max_customer_concentration:
        risks.append("Customer concentration over 30%")
    if not _number(row["sde"]):
        risks.append("Missing SDE")
    if not _number(row["asking_price"]):
        risks.append("Missing asking price")
    if "owner operator" in text or "owner-operated" in text:
        risks.append("May require owner presence")
    return "; ".join(risks) if risks else "No major rule-based red flags found"


def _recommendation(total: int, risks: str) -> str:
    if total >= 75 and "Avoid-list" not in risks:
        return "Pursue now"
    if total >= 60:
        return "Review manually"
    if total >= 45:
        return "Keep warm"
    return "Pass unless new information improves fit"


def _text(row: Row) -> str:
    values = [
        row["title"],
        row["industry"],
        row["city"],
        row["state"],
        row["region"],
        row["description"],
        row["source_name"],
    ]
    return " ".join(str(value).lower() for value in values if value)


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
