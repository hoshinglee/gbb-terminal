from datetime import date, datetime, timedelta

from gbb_terminal.decision_center.engine import analyze_expression, process_outcome_classification, stress_expression
from gbb_terminal.decision_center.models import (
    InstrumentExpression,
    PositionIntent,
    StressScenarioInput,
    StressTestRequest,
)
from gbb_terminal.options.models import OptionLeg, OptionSimulationRequest
from gbb_terminal.portfolio.models import PortfolioContext, RiskPolicy


NOW = datetime(2026, 8, 20, 12)


def context(cash: float = 50_000) -> PortfolioContext:
    return PortfolioContext(
        context_id="personal",
        investable_value=100_000,
        liquid_cash=cash,
        base_currency="USD",
        created_at=NOW,
        updated_at=NOW,
    )


def policy() -> RiskPolicy:
    return RiskPolicy(
        policy_id="policy-1",
        policy_key="personal-default",
        version=1,
        name="Personal Policy",
        normal_target_position_percent=10,
        max_single_name_exposure_percent=25,
        max_assignment_exposure_percent=15,
        max_short_option_collateral_percent=20,
        min_unencumbered_cash_reserve_percent=None,
        min_unencumbered_cash_reserve_amount=20_000,
        portfolio_stress_loss_ceiling_percent=20,
        created_at=NOW,
    )


def intent(current: float = 0, shares: float = 0, maximum: float = 21_000) -> PositionIntent:
    return PositionIntent(
        intent_id="intent-1",
        intent_key="company:nvda",
        company_id="company-nvda",
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        version=1,
        target_amount=14_000,
        target_percent=14,
        maximum_amount=maximum,
        maximum_percent=maximum / 1000,
        current_exposure_amount=current,
        current_exposure_percent=current / 1000,
        current_shares=shares,
        investable_value=100_000,
        is_complete=True,
        warnings=[],
        created_at=NOW,
    )


def csp(strike: float = 100, premium: float = 3) -> InstrumentExpression:
    position = OptionSimulationRequest(
        ticker="NVDA",
        underlying_price=110,
        position_kind="cash_secured_put",
        legs=[
            OptionLeg(
                option_type="put",
                side="short",
                strike=strike,
                expiration=date.today() + timedelta(days=90),
                premium=premium,
                implied_volatility=0.35,
            )
        ],
        paths=50,
    )
    return InstrumentExpression(kind="option", name="Cash-Secured Put", option_position=position)


def call_spread() -> InstrumentExpression:
    position = OptionSimulationRequest(
        ticker="NVDA",
        underlying_price=100,
        position_kind="bull_call_spread",
        legs=[
            OptionLeg(
                option_type="call",
                side="long",
                strike=100,
                expiration=date.today() + timedelta(days=90),
                premium=8,
                implied_volatility=0.3,
            ),
            OptionLeg(
                option_type="call",
                side="short",
                strike=120,
                expiration=date.today() + timedelta(days=90),
                premium=3,
                implied_volatility=0.3,
            ),
        ],
        paths=50,
    )
    return InstrumentExpression(kind="option", name="Bull Call Spread", option_position=position)


def test_direct_shares_size_from_position_intent_before_instrument_choice():
    result = analyze_expression(
        intent(),
        InstrumentExpression(kind="direct_shares", name="Direct Shares", share_price=100),
        context(),
        policy(),
        "ownership_now",
    )

    assert result.expression.share_quantity == 140
    assert result.capital_required == 14_000
    assert result.overall_status == "pass"
    assert "one-share increments" in result.sizing_flexibility


def test_fitting_and_oversized_csp_show_assignment_granularity_and_policy_math():
    fitting = analyze_expression(intent(), csp(), context(), policy(), "accumulate_lower")
    oversized = analyze_expression(intent(maximum=21_000), csp(strike=300), context(), policy(), "income")

    assert fitting.assignment_obligation == 10_000
    assert fitting.effective_acquisition_basis == 97
    assert fitting.shares_after_assignment == 100
    assert fitting.overall_status == "pass"
    assert oversized.assignment_obligation == 30_000
    assert oversized.overall_status == "fail"
    mismatch = next(check for check in oversized.checks if check.key == "instrument_size_mismatch")
    assert mismatch.status == "fail"
    assert "One standard contract" in mismatch.reason


def test_existing_concentration_and_cash_reserve_fail_independently():
    concentrated = analyze_expression(intent(current=20_000, shares=100), csp(), context(), policy(), "income")
    cash_constrained = analyze_expression(intent(), csp(), context(cash=25_000), policy(), "income")

    assert next(check for check in concentrated.checks if check.key == "single_name").status == "fail"
    assert next(check for check in cash_constrained.checks if check.key == "cash_reserve").status == "fail"


def test_missing_portfolio_context_is_explicitly_incomplete():
    result = analyze_expression(intent(), csp(), None, None, "accumulate_lower")

    assert result.overall_status == "incomplete"
    assert all(check.status == "incomplete" for check in result.checks)


def test_objective_changes_explanation_without_claiming_an_optimum():
    ownership = analyze_expression(intent(), csp(), context(), policy(), "ownership_now")
    accumulation = analyze_expression(intent(), csp(), context(), policy(), "accumulate_lower")

    assert ownership.objective_fit != accumulation.objective_fit
    assert "miss immediate upside" in ownership.objective_fit
    assert "acquire" in accumulation.objective_fit


def test_share_csp_and_defined_risk_stress_use_portfolio_context():
    share_expression = InstrumentExpression(
        kind="direct_shares",
        name="Direct Shares",
        share_quantity=140,
        share_price=100,
    )
    share_stress = stress_expression(
        "NVDA",
        intent(),
        StressTestRequest(expression=share_expression),
        context(),
        policy(),
    )
    csp_stress = stress_expression(
        "NVDA",
        intent(),
        StressTestRequest(expression=csp(), scenarios=[StressScenarioInput(underlying_change_percent=-40)]),
        context(),
        policy(),
    )
    spread_stress = stress_expression(
        "NVDA",
        intent(),
        StressTestRequest(
            expression=call_spread(),
            scenarios=[StressScenarioInput(underlying_change_percent=-20, iv_change_percent=50, days_forward=30)],
        ),
        context(),
        policy(),
    )

    assert share_stress.scenarios[0].position_pnl == -2_800
    assert csp_stress.scenarios[0].assignment_obligation == 10_000
    assert spread_stress.scenarios[0].assumptions[0].startswith("Option values use the server-side")


def test_process_and_outcome_classification_remain_separate():
    assert process_outcome_classification("good", "unfavorable") == "good_process_unfavorable_outcome"
    assert process_outcome_classification("poor", "favorable") == "poor_process_favorable_outcome"
    assert process_outcome_classification("mixed", "favorable") is None
