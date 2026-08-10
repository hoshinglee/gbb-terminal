from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


METRIC_DEFINITION_VERSION = "1.0.0"


class MetricBehavior(StrEnum):
    FLOW = "flow"
    INSTANT = "instant"
    PER_SHARE = "per_share"
    AVERAGE = "average"


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    label: str
    unit: str
    behavior: MetricBehavior
    concepts: tuple[str, ...]
    exposed: bool = True
    absolute_value: bool = False


METRIC_DEFINITIONS = {
    "revenue": MetricDefinition(
        "revenue",
        "Revenue",
        "USD",
        MetricBehavior.FLOW,
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    ),
    "gross_profit": MetricDefinition(
        "gross_profit",
        "Gross Profit",
        "USD",
        MetricBehavior.FLOW,
        ("GrossProfit",),
    ),
    "operating_income": MetricDefinition(
        "operating_income",
        "Operating Income",
        "USD",
        MetricBehavior.FLOW,
        ("OperatingIncomeLoss",),
    ),
    "net_income": MetricDefinition(
        "net_income",
        "Net Income",
        "USD",
        MetricBehavior.FLOW,
        ("NetIncomeLoss", "ProfitLoss"),
    ),
    "diluted_eps": MetricDefinition(
        "diluted_eps",
        "Diluted EPS",
        "USD/share",
        MetricBehavior.PER_SHARE,
        ("EarningsPerShareDiluted", "EarningsPerShareDilutedIncludingExtraordinaryItems"),
    ),
    "operating_cash_flow": MetricDefinition(
        "operating_cash_flow",
        "Operating Cash Flow",
        "USD",
        MetricBehavior.FLOW,
        (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
    ),
    "capital_expenditure": MetricDefinition(
        "capital_expenditure",
        "Capital Expenditure",
        "USD",
        MetricBehavior.FLOW,
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
        ),
        absolute_value=True,
    ),
    "cash": MetricDefinition(
        "cash",
        "Cash",
        "USD",
        MetricBehavior.INSTANT,
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
    ),
    "debt": MetricDefinition(
        "debt",
        "Debt",
        "USD",
        MetricBehavior.INSTANT,
        ("LongTermDebtAndFinanceLeaseObligations", "LongTermDebt"),
    ),
    "diluted_shares": MetricDefinition(
        "diluted_shares",
        "Diluted Shares",
        "shares",
        MetricBehavior.AVERAGE,
        ("WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"),
    ),
    "stockholders_equity": MetricDefinition(
        "stockholders_equity",
        "Stockholders' Equity",
        "USD",
        MetricBehavior.INSTANT,
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        exposed=False,
    ),
    "pretax_income": MetricDefinition(
        "pretax_income",
        "Pretax Income",
        "USD",
        MetricBehavior.FLOW,
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
        exposed=False,
    ),
    "income_tax_expense": MetricDefinition(
        "income_tax_expense",
        "Income Tax Expense",
        "USD",
        MetricBehavior.FLOW,
        ("IncomeTaxExpenseBenefit",),
        exposed=False,
    ),
}


DEBT_COMPONENT_CONCEPTS = (
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "ShortTermBorrowings",
    "CurrentPortionOfLongTermDebt",
)


DEBT_COMPONENT_GROUPS = (
    ("LongTermDebtCurrent", "CurrentPortionOfLongTermDebt"),
    ("LongTermDebtNoncurrent",),
    ("ShortTermBorrowings",),
)


DERIVED_METRICS = {
    "free_cash_flow": ("Free Cash Flow", "USD"),
    "revenue_growth": ("Revenue Growth", "%"),
    "eps_growth": ("EPS Growth", "%"),
    "gross_margin": ("Gross Margin", "%"),
    "operating_margin": ("Operating Margin", "%"),
    "fcf_margin": ("FCF Margin", "%"),
    "return_on_equity": ("Return On Equity", "%"),
    "return_on_invested_capital": ("Return On Invested Capital", "%"),
    "net_debt": ("Net Debt", "USD"),
    "share_dilution": ("Share Dilution", "%"),
}
