import pytest
from pydantic import ValidationError

from gbb_terminal.portfolio.models import PortfolioContextInput, PortfolioPositionInput, RiskPolicyInput


def test_liquid_cash_must_fit_inside_investable_value():
    with pytest.raises(ValidationError, match="Liquid cash cannot exceed"):
        PortfolioContextInput(investable_value=100_000, liquid_cash=120_000)


def test_position_preserves_short_share_context_and_manual_value():
    position = PortfolioPositionInput(
        ticker=" nvda ",
        shares=-10,
        cost_basis_per_share=200,
        manual_market_value=-1_900,
    )

    assert position.ticker == "NVDA"
    assert position.shares == -10
    assert position.manual_market_value == -1_900


def test_policy_requires_explicit_cash_reserve_and_coherent_position_limits():
    with pytest.raises(ValidationError, match="Define the minimum cash reserve"):
        RiskPolicyInput(
            name="No Reserve",
            normal_target_position_percent=8,
            max_single_name_exposure_percent=15,
            max_assignment_exposure_percent=15,
            max_short_option_collateral_percent=20,
            portfolio_stress_loss_ceiling_percent=25,
        )
    with pytest.raises(ValidationError, match="Normal target position cannot exceed"):
        RiskPolicyInput(
            name="Inverted Limits",
            normal_target_position_percent=20,
            max_single_name_exposure_percent=15,
            max_assignment_exposure_percent=15,
            max_short_option_collateral_percent=20,
            min_unencumbered_cash_reserve_percent=10,
            portfolio_stress_loss_ceiling_percent=25,
        )
