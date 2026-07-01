"""Outreach and diligence draft generation."""

from __future__ import annotations

from sqlite3 import Row


def owner_outreach(row: Row) -> str:
    """Create a concise owner-direct outreach draft."""

    company = row["company_name"] or "your business"
    industry = row["industry"] or "your industry"
    location = ", ".join(part for part in (row["city"], row["state"]) if part)
    location_phrase = f" in {location}" if location else ""
    return (
        f"Subject: Confidential conversation about {company}\n\n"
        f"Hi,\n\n"
        f"I am looking to acquire and personally operate one strong {industry} business{location_phrase}. "
        f"{company} stood out because it appears to fit the kind of durable, operations-heavy company "
        f"I am focused on.\n\n"
        f"If you would ever consider a confidential succession or majority-sale conversation, I would be "
        f"grateful for 15 minutes. I can move quietly, respect your team and customers, and only continue "
        f"if there is a clear fit.\n\n"
        f"Best,\n"
    )


def broker_questions(row: Row) -> str:
    """Generate broker questions for a listing."""

    return "\n".join(
        [
            f"Questions for {row['title']}:",
            "1. What is included in SDE add-backs, and which add-backs are recurring?",
            "2. What percentage of revenue comes from the top customer and top five customers?",
            "3. How much owner involvement is required weekly, and in which functions?",
            "4. Are operations manager, dispatcher, sales, and finance roles already staffed?",
            "5. Is the deal SBA financeable, and has any lender reviewed it?",
            "6. What working capital is required at close?",
            "7. Are there customer contracts, route density, fleet leases, or facility leases to review?",
            "8. Why is the seller exiting, and what transition support will they provide?",
        ]
    )


def diligence_checklist(row: Row) -> str:
    """Generate an initial diligence checklist."""

    return "\n".join(
        [
            f"Initial due diligence checklist for {row['title']}:",
            "- Three years of P&L, balance sheet, tax returns, and monthly trailing twelve-month statements",
            "- SDE add-back support and owner payroll normalization",
            "- Customer revenue concentration report",
            "- Employee roster, compensation, tenure, and key-person dependency notes",
            "- Fleet, equipment, lease, and maintenance schedules where applicable",
            "- Facility lease, renewal options, landlord consent requirements",
            "- Insurance loss runs, claims, licenses, permits, and regulatory compliance",
            "- Customer contracts, recurring revenue, churn, and gross margin by service line",
            "- SBA lender package: CIM, tax returns, debt schedule, lease, and buyer resume",
        ]
    )
