"""SBA acquisition financial model calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FinancingInputs:
    purchase_price: float
    sde: float
    down_payment: float
    interest_rate: float = 0.11
    term_years: int = 10
    seller_note: float = 0
    working_capital: float = 0
    target_dscr: float = 1.25


@dataclass(frozen=True)
class FinancingResult:
    purchase_price: float
    down_payment: float
    sba_loan: float
    seller_note: float
    interest_rate: float
    term_years: int
    monthly_payment: float
    annual_debt_service: float
    dscr: float | None
    cash_on_cash: float | None
    post_debt_owner_income: float
    breakeven_sde: float
    working_capital: float
    maximum_offer: float
    roi: float | None
    assumptions: dict[str, float | int]


def monthly_payment(principal: float, annual_rate: float, term_years: int) -> float:
    """Calculate the amortizing monthly payment."""

    if principal <= 0:
        return 0.0
    months = term_years * 12
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / months
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def model_financing(inputs: FinancingInputs) -> FinancingResult:
    """Build a simple SBA model for one acquisition scenario."""

    sba_loan = max(inputs.purchase_price - inputs.down_payment - inputs.seller_note, 0)
    payment = monthly_payment(sba_loan, inputs.interest_rate, inputs.term_years)
    annual_debt = payment * 12
    post_debt_income = inputs.sde - annual_debt
    total_cash_in = inputs.down_payment + inputs.working_capital
    dscr = inputs.sde / annual_debt if annual_debt else None
    cash_on_cash = post_debt_income / total_cash_in if total_cash_in else None
    breakeven_sde = annual_debt
    max_debt_service = inputs.sde / inputs.target_dscr if inputs.target_dscr else inputs.sde
    max_loan = _loan_principal_from_payment(max_debt_service / 12, inputs.interest_rate, inputs.term_years)
    maximum_offer = max_loan + inputs.down_payment + inputs.seller_note
    roi = post_debt_income / inputs.purchase_price if inputs.purchase_price else None
    return FinancingResult(
        purchase_price=round(inputs.purchase_price, 2),
        down_payment=round(inputs.down_payment, 2),
        sba_loan=round(sba_loan, 2),
        seller_note=round(inputs.seller_note, 2),
        interest_rate=inputs.interest_rate,
        term_years=inputs.term_years,
        monthly_payment=round(payment, 2),
        annual_debt_service=round(annual_debt, 2),
        dscr=round(dscr, 2) if dscr is not None else None,
        cash_on_cash=round(cash_on_cash, 2) if cash_on_cash is not None else None,
        post_debt_owner_income=round(post_debt_income, 2),
        breakeven_sde=round(breakeven_sde, 2),
        working_capital=round(inputs.working_capital, 2),
        maximum_offer=round(maximum_offer, 2),
        roi=round(roi, 2) if roi is not None else None,
        assumptions=asdict(inputs),
    )


def sensitivity(inputs: FinancingInputs) -> list[FinancingResult]:
    """Generate rate and purchase price sensitivity cases."""

    cases: list[FinancingResult] = []
    for price_factor in (0.9, 1.0, 1.1):
        for rate_delta in (-0.01, 0.0, 0.01):
            cases.append(
                model_financing(
                    FinancingInputs(
                        purchase_price=inputs.purchase_price * price_factor,
                        sde=inputs.sde,
                        down_payment=inputs.down_payment,
                        interest_rate=max(inputs.interest_rate + rate_delta, 0),
                        term_years=inputs.term_years,
                        seller_note=inputs.seller_note,
                        working_capital=inputs.working_capital,
                        target_dscr=inputs.target_dscr,
                    )
                )
            )
    return cases


def _loan_principal_from_payment(monthly: float, annual_rate: float, term_years: int) -> float:
    months = term_years * 12
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return monthly * months
    return monthly * (1 - (1 + monthly_rate) ** -months) / monthly_rate
