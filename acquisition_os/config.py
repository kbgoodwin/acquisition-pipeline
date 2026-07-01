"""Configuration and investment criteria."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


WORKFLOW_STAGES: tuple[str, ...] = (
    "Prospect",
    "Contacted",
    "Broker Response",
    "NDA Requested",
    "NDA Signed",
    "Financials Received",
    "Initial Review",
    "Seller Call",
    "Site Visit",
    "LOI Drafted",
    "LOI Submitted",
    "LOI Accepted",
    "Due Diligence",
    "Financing",
    "Closing Attorney",
    "Insurance",
    "Bank Approval",
    "Closing",
    "Integration",
)


@dataclass(frozen=True)
class Criteria:
    """Acquisition mandate used by scoring, reports, and filters."""

    target_sde_min: int = 300_000
    target_sde_max: int = 600_000
    price_min: int = 750_000
    price_max: int = 2_500_000
    equity_min: int = 100_000
    equity_max: int = 150_000
    owner_income_min: int = 200_000
    owner_income_goal: int = 300_000
    max_customer_concentration: float = 0.30
    highest_priority_industries: tuple[str, ...] = (
        "warehouse",
        "3pl",
        "fulfillment",
        "distribution",
        "small trucking fleet",
        "final mile delivery",
        "courier",
        "commercial moving",
        "storage",
        "cold storage",
        "agricultural logistics",
        "fleet maintenance",
        "equipment rental",
        "packaging",
        "industrial services",
    )
    second_priority_industries: tuple[str, ...] = (
        "commercial cleaning",
        "staffing",
        "security",
        "hvac",
        "plumbing",
        "electrical",
    )
    avoid_industries: tuple[str, ...] = (
        "restaurant",
        "retail",
        "freight brokerage",
        "freight broker",
        "owner presence franchise",
    )
    primary_geographies: tuple[str, ...] = (
        "atlanta",
        "marietta",
        "norcross",
        "duluth",
        "lawrenceville",
        "savannah",
        "macon",
        "augusta",
        "columbus, ga",
        "georgia",
    )
    secondary_geographies: tuple[str, ...] = (
        "fresno",
        "porterville",
        "visalia",
        "clovis",
        "hanford",
        "tulare",
        "bakersfield",
        "madera",
        "central california",
    )
    third_geographies: tuple[str, ...] = (
        "cincinnati",
        "dayton",
        "columbus, oh",
        "northern kentucky",
        "lexington",
        "louisville",
    )


@dataclass(frozen=True)
class Settings:
    """Runtime paths for the local system."""

    data_dir: Path = field(default_factory=lambda: Path("data"))
    database_path: Path = field(default_factory=lambda: Path("data/acquisition_os.sqlite3"))
    output_dir: Path = field(default_factory=lambda: Path("outputs"))


DEFAULT_CRITERIA = Criteria()
DEFAULT_SETTINGS = Settings()
