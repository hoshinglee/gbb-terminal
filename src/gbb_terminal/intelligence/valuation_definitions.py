from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


VALUATION_ENGINE_VERSION = "1.0.0"


class ValuationFormula(StrEnum):
    MARKET_CAP_RATIO = "market_cap_ratio"
    ENTERPRISE_VALUE_RATIO = "enterprise_value_ratio"
    YIELD = "yield"


@dataclass(frozen=True)
class ValuationDefinition:
    metric_id: str
    label: str
    unit: str
    formula: ValuationFormula
    denominator_metric: str


VALUATION_DEFINITIONS = {
    "trailing_pe": ValuationDefinition(
        "trailing_pe",
        "Trailing P/E",
        "x",
        ValuationFormula.MARKET_CAP_RATIO,
        "net_income",
    ),
    "price_to_sales": ValuationDefinition(
        "price_to_sales",
        "Price / Sales",
        "x",
        ValuationFormula.MARKET_CAP_RATIO,
        "revenue",
    ),
    "price_to_book": ValuationDefinition(
        "price_to_book",
        "Price / Book",
        "x",
        ValuationFormula.MARKET_CAP_RATIO,
        "stockholders_equity",
    ),
    "ev_to_revenue": ValuationDefinition(
        "ev_to_revenue",
        "EV / Revenue",
        "x",
        ValuationFormula.ENTERPRISE_VALUE_RATIO,
        "revenue",
    ),
    "ev_to_ebitda": ValuationDefinition(
        "ev_to_ebitda",
        "EV / EBITDA",
        "x",
        ValuationFormula.ENTERPRISE_VALUE_RATIO,
        "ebitda",
    ),
    "price_to_fcf": ValuationDefinition(
        "price_to_fcf",
        "Price / FCF",
        "x",
        ValuationFormula.MARKET_CAP_RATIO,
        "free_cash_flow",
    ),
    "earnings_yield": ValuationDefinition(
        "earnings_yield",
        "Earnings Yield",
        "%",
        ValuationFormula.YIELD,
        "net_income",
    ),
    "fcf_yield": ValuationDefinition(
        "fcf_yield",
        "FCF Yield",
        "%",
        ValuationFormula.YIELD,
        "free_cash_flow",
    ),
}
