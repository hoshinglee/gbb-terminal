from datetime import date, timedelta

import pytest

from gbb_terminal.options.models import OptionPlanRequest, OptionScenarioRequest, OptionSimulationRequest
from gbb_terminal.options.planner import build_option_plan, scenario_position, select_plan_expiration


def option_chain(expiration: date) -> dict:
    def contracts(option_type: str) -> list[dict]:
        return [
            {
                "contract": f"TEST{expiration:%y%m%d}{option_type[0].upper()}{strike:08d}",
                "strike": strike,
                "last": 4.25,
                "bid": round(max(0.5, 5 - abs(strike - 100) * 0.12), 2),
                "ask": round(max(0.75, 5.4 - abs(strike - 100) * 0.12), 2),
                "mid": round(max(0.625, 5.2 - abs(strike - 100) * 0.12), 2),
                "spread": 0.4,
                "volume": 100,
                "openInterest": 500,
                "iv": 30,
                "quoteQuality": "Two-Sided",
            }
            for strike in (80, 90, 95, 100, 105, 110, 120)
        ]

    value = expiration.isoformat()
    return {
        "expiration": value,
        "defaultExpiration": value,
        "expirations": [value],
        "calls": contracts("call"),
        "puts": contracts("put"),
        "source": "Fixture",
        "dataStatus": {
            "source": "Fixture",
            "status": "Delayed",
            "knownAt": f"{date.today().isoformat()}T20:00:00+00:00",
            "qualityWarnings": ["Fixture quotes are delayed."],
        },
    }


def request(outlook: str, **overrides) -> OptionPlanRequest:
    return OptionPlanRequest.model_validate({
        "ticker": "TEST",
        "outlook": outlook,
        "target_date": (date.today() + timedelta(days=45)).isoformat(),
        **overrides,
    })


@pytest.mark.parametrize(
    ("outlook", "expected"),
    [
        ("bullish", {"long_call", "bull_call_spread", "bull_put_spread"}),
        ("bearish", {"long_put", "bear_put_spread", "bear_call_spread"}),
    ],
)
def test_planner_builds_only_validated_supported_directional_structures(outlook, expected):
    expiration = date.today() + timedelta(days=60)
    result = build_option_plan(request(outlook), 100, option_chain(expiration))

    assert {candidate["positionKind"] for candidate in result["candidates"]} == expected
    assert "short_call" not in {candidate["positionKind"] for candidate in result["candidates"]}
    for candidate in result["candidates"]:
        OptionSimulationRequest.model_validate(candidate["position"])
        assert candidate["quoteQuality"] == "Two-Sided"
        assert candidate["quotes"]


def test_planner_respects_share_ownership_and_acquisition_context():
    expiration = date.today() + timedelta(days=60)
    result = build_option_plan(
        request("neutral", shares_owned=100, acquiring_shares_acceptable=True),
        100,
        option_chain(expiration),
    )

    kinds = {candidate["positionKind"] for candidate in result["candidates"]}
    assert kinds == {"covered_call", "cash_secured_put", "bear_call_spread"}
    covered = next(candidate for candidate in result["candidates"] if candidate["positionKind"] == "covered_call")
    assert covered["position"]["shares"] == 100
    assert covered["netCredit"] > 0


def test_neutral_planner_explains_directional_fallback_without_share_context():
    expiration = date.today() + timedelta(days=60)
    result = build_option_plan(request("neutral"), 100, option_chain(expiration))

    assert {candidate["positionKind"] for candidate in result["candidates"]} == {"bear_call_spread", "bull_put_spread"}
    assert any("retain directional exposure" in warning for warning in result["warnings"])


def test_low_budget_is_visible_without_claiming_a_candidate_fits():
    expiration = date.today() + timedelta(days=60)
    result = build_option_plan(
        request("bullish", maximum_loss=1, capital_budget=1),
        100,
        option_chain(expiration),
    )

    assert all(not candidate["withinBudget"] for candidate in result["candidates"])
    assert any("No candidate fits" in warning for warning in result["warnings"])


def test_planner_uses_long_ask_and_short_bid_quotes():
    expiration = date.today() + timedelta(days=60)
    result = build_option_plan(request("bullish"), 100, option_chain(expiration))
    spread = next(candidate for candidate in result["candidates"] if candidate["positionKind"] == "bull_call_spread")

    assert [quote["premiumSource"] for quote in spread["quotes"]] == ["ask", "bid"]
    assert spread["position"]["legs"][0]["premium"] == spread["quotes"][0]["ask"]
    assert spread["position"]["legs"][1]["premium"] == spread["quotes"][1]["bid"]


def test_scenario_uses_server_pricing_and_warns_beyond_expiry():
    expiration = date.today() + timedelta(days=30)
    plan = build_option_plan(request("bullish"), 100, option_chain(expiration))
    position = plan["candidates"][0]["position"]
    scenario = OptionScenarioRequest.model_validate({
        "position": position,
        "scenario_price": 115,
        "scenario_date": (expiration + timedelta(days=1)).isoformat(),
    })

    result = scenario_position(scenario)

    assert result["scenarioPrice"] == 115
    assert result["remainingDays"] == 0
    assert result["modeledPositionValue"] > 0
    assert result["pnl"] > 0
    assert set(result["greeks"]) == {"delta", "gamma", "theta", "vega"}
    assert any("beyond at least one leg's expiry" in warning for warning in result["warnings"])


def test_expiration_selection_uses_latest_available_with_explicit_warning():
    first = date.today() + timedelta(days=30)
    last = date.today() + timedelta(days=60)
    selected, warnings = select_plan_expiration(
        [first.isoformat(), last.isoformat()],
        date.today() + timedelta(days=180),
    )

    assert selected == last.isoformat()
    assert warnings
