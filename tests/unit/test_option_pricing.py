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

