from datetime import date, timedelta

import pytest

from gbb_terminal.options.models import OptionSimulationRequest
from gbb_terminal.options.pricing import american_option_price, black_scholes_price
from gbb_terminal.options.simulation import simulate_position


def test_american_put_is_not_below_european_put():
    american = american_option_price("put", 90, 100, 0.5, 0.25, 0.04)
    european = black_scholes_price("put", 90, 100, 0.5, 0.25, 0.04)
    assert american >= european - 0.02
    assert american >= 10


def test_long_call_expiry_payoff_is_reconciled():
    request = OptionSimulationRequest.model_validate({
        "ticker": "AAPL",
        "underlying_price": 100,
        "position_kind": "long_call",
        "paths": 50,
        "legs": [{"option_type": "call", "side": "long", "strike": 100, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 5, "quantity": 1, "implied_volatility": 0.25}],
    })
    result = simulate_position(request)
    point = min(result["payoff"], key=lambda item: abs(item["underlyingPrice"] - 120))
    assert point["pnl"] == pytest.approx(1500, abs=2)
    assert result["historicalStatus"] == "Theoretical Simulation"


def test_conversion_has_locked_payoff_and_financing_analysis():
    expiration = date.today() + timedelta(days=365)
    request = OptionSimulationRequest.model_validate({
        "ticker": "TEST",
        "underlying_price": 1200,
        "position_kind": "conversion",
        "shares": 100,
        "share_cost_basis": 1200,
        "interest_rate": 0.04,
        "paths": 50,
        "legs": [
            {"option_type": "put", "side": "long", "strike": 1200, "expiration": expiration.isoformat(), "premium": 637, "quantity": 1, "implied_volatility": 0.3},
            {"option_type": "call", "side": "short", "strike": 1200, "expiration": expiration.isoformat(), "premium": 753, "quantity": 1, "implied_volatility": 0.3},
        ],
    })
    result = simulate_position(request)

    assert {point["pnl"] for point in result["payoff"]} == {11600.0}
    assert result["conversionAnalysis"]["lockedTerminalProceeds"] == 120000
    assert result["conversionAnalysis"]["netCapitalCommitted"] == 108400
    assert result["conversionAnalysis"]["nominalReturnPercent"] == 10.7011
    assert "risk-free" not in result["conversionAnalysis"]["interpretation"].lower()


def test_conversion_rejects_mismatched_strikes():
    with pytest.raises(ValueError, match="same strike"):
        OptionSimulationRequest.model_validate({
            "ticker": "TEST",
            "underlying_price": 100,
            "position_kind": "conversion",
            "shares": 100,
            "paths": 50,
            "legs": [
                {"option_type": "put", "side": "long", "strike": 95, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 4, "quantity": 1, "implied_volatility": 0.25},
                {"option_type": "call", "side": "short", "strike": 105, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 4, "quantity": 1, "implied_volatility": 0.25},
            ],
        })


def test_bear_call_spread_is_not_mislabeled_as_uncapped():
    expiration = date.today() + timedelta(days=60)
    request = OptionSimulationRequest.model_validate({
        "ticker": "TEST",
        "underlying_price": 100,
        "position_kind": "bear_call_spread",
        "paths": 50,
        "legs": [
            {"option_type": "call", "side": "short", "strike": 100, "expiration": expiration, "premium": 5, "quantity": 1, "implied_volatility": 0.25},
            {"option_type": "call", "side": "long", "strike": 110, "expiration": expiration, "premium": 2, "quantity": 1, "implied_volatility": 0.25},
        ],
    })

    result = simulate_position(request)

    assert result["positionProfile"]["riskLabel"] == "Structure-Dependent Risk"
    assert result["summary"]["maximumLoss"] != "Unlimited"
