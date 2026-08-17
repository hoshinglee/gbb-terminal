from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from .analysis import conversion_financing_analysis, management_playbook, position_profile
from .models import OptionLeg, OptionSimulationRequest, OptionType, PositionSide
from .pricing import american_option_price, black_scholes_price, option_greeks, probability_in_the_money


def _years(expiration: date, elapsed_days: int = 0) -> float:
    return max((expiration - date.today()).days - elapsed_days, 0) / 365


def years_to_expiration(expiration: date, valuation_date: date | None = None) -> float:
    return max((expiration - (valuation_date or date.today())).days, 0) / 365


def option_leg_mark(leg: OptionLeg, spot: float, request: OptionSimulationRequest, valuation_date: date | None = None) -> float:
    years = years_to_expiration(leg.expiration, valuation_date)
    return american_option_price(leg.option_type, spot, leg.strike, years, leg.implied_volatility, request.interest_rate, request.dividend_yield)


def position_value_at(request: OptionSimulationRequest, spot: float, valuation_date: date | None = None) -> dict[str, float]:
    option_value = 0.0
    for leg in request.legs:
        direction = 1 if leg.side == PositionSide.LONG else -1
        option_value += direction * option_leg_mark(leg, spot, request, valuation_date) * leg.quantity * leg.multiplier
    share_value = request.shares * spot
    return {
        "optionValue": round(option_value, 2),
        "shareValue": round(share_value, 2),
        "positionValue": round(option_value + share_value, 2),
    }


def position_pnl_at(request: OptionSimulationRequest, spot: float, valuation_date: date | None = None) -> float:
    option_pnl = 0.0
    for leg in request.legs:
        direction = 1 if leg.side == PositionSide.LONG else -1
        option_pnl += direction * (option_leg_mark(leg, spot, request, valuation_date) - leg.premium) * leg.quantity * leg.multiplier
    share_basis = request.share_cost_basis or request.underlying_price
    return round(option_pnl + request.shares * (spot - share_basis), 2)


def position_greeks_at(request: OptionSimulationRequest, spot: float, valuation_date: date | None = None) -> dict[str, Any]:
    legs = []
    aggregate = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in request.legs:
        years = years_to_expiration(leg.expiration, valuation_date)
        direction = 1 if leg.side == PositionSide.LONG else -1
        scale = direction * leg.quantity * leg.multiplier
        values = option_greeks(leg.option_type, spot, leg.strike, years, leg.implied_volatility, request.interest_rate, request.dividend_yield)
        price = values.pop("price")
        scaled = {key: round(value * scale, 4) for key, value in values.items()}
        for key in aggregate:
            aggregate[key] += scaled[key]
        legs.append({
            "legId": leg.leg_id,
            "optionType": leg.option_type,
            "side": leg.side,
            "strike": leg.strike,
            "americanPrice": price,
            "blackScholesPrice": round(black_scholes_price(leg.option_type, spot, leg.strike, years, leg.implied_volatility, request.interest_rate, request.dividend_yield), 4),
            "probabilityInTheMoney": round(probability_in_the_money(leg.option_type, spot, leg.strike, years, leg.implied_volatility, request.interest_rate, request.dividend_yield) * 100, 1),
            **scaled,
        })
    return {
        "legs": legs,
        "aggregate": {key: round(value, 4) for key, value in aggregate.items()},
    }


def _leg_value(leg: OptionLeg, spot: float, elapsed_days: int, request: OptionSimulationRequest) -> float:
    valuation_date = date.fromordinal(date.today().toordinal() + elapsed_days)
    mark = option_leg_mark(leg, spot, request, valuation_date)
    direction = 1 if leg.side == PositionSide.LONG else -1
    return direction * (mark - leg.premium) * leg.quantity * leg.multiplier


def _position_pnl(request: OptionSimulationRequest, spot: float, elapsed_days: int) -> float:
    option_pnl = sum(_leg_value(leg, spot, elapsed_days, request) for leg in request.legs)
    share_basis = request.share_cost_basis or request.underlying_price
    return option_pnl + request.shares * (spot - share_basis)


def _summary(request: OptionSimulationRequest, payoff: list[dict[str, float]]) -> dict[str, Any]:
    values = np.array([point["pnl"] for point in payoff])
    spots = np.array([point["underlyingPrice"] for point in payoff])
    crossings: list[float] = []
    for index in range(1, len(values)):
        previous_value, current_value = values[index - 1], values[index]
        if previous_value == 0:
            crossings.append(float(spots[index - 1]))
        elif current_value == 0:
            crossings.append(float(spots[index]))
        elif previous_value * current_value < 0:
            weight = -previous_value / (current_value - previous_value)
            crossings.append(float(spots[index - 1] + weight * (spots[index] - spots[index - 1])))
    from .lifecycle import position_collateral

    high_price_slope = request.shares + sum((1 if leg.side == PositionSide.LONG else -1) * leg.quantity * leg.multiplier for leg in request.legs if leg.option_type == OptionType.CALL)
    return {
        "breakEvens": [round(value, 2) for value in crossings],
        "maximumGain": "Unlimited" if high_price_slope > 0 else round(float(values.max()), 2),
        "maximumLoss": "Unlimited" if high_price_slope < 0 else round(float(values.min()), 2),
        "collateral": round(position_collateral(request.legs, {}, request.shares), 2),
        "assignmentExposure": round(sum(leg.strike * leg.quantity * leg.multiplier for leg in request.legs if leg.side == PositionSide.SHORT), 2),
    }


def position_comparison(request: OptionSimulationRequest) -> dict[str, Any]:
    maximum_days = max(max((leg.expiration - date.today()).days, 0) for leg in request.legs)
    largest_strike = max(leg.strike for leg in request.legs)
    spot_grid = np.linspace(0, max(request.underlying_price * 2, largest_strike * 2), 161)
    payoff = [{"underlyingPrice": round(float(spot), 2), "pnl": round(_position_pnl(request, float(spot), maximum_days), 2)} for spot in spot_grid]
    return {
        "summary": _summary(request, payoff),
        "positionProfile": position_profile(request),
        "greeks": position_greeks_at(request, request.underlying_price),
    }


def simulate_position(request: OptionSimulationRequest) -> dict[str, Any]:
    maximum_days = max(max((leg.expiration - date.today()).days, 0) for leg in request.legs)
    largest_strike = max(leg.strike for leg in request.legs)
    spot_grid = np.linspace(0, max(request.underlying_price * 2, largest_strike * 2), 161)
    payoff = [{"underlyingPrice": round(float(spot), 2), "pnl": round(_position_pnl(request, float(spot), maximum_days), 2)} for spot in spot_grid]
    timeline_days = sorted(set(int(maximum_days * fraction) for fraction in (0, 0.25, 0.5, 0.75, 1)))
    surface = [{"day": day, "points": [{"underlyingPrice": round(float(spot), 2), "pnl": round(_position_pnl(request, float(spot), day), 2)} for spot in spot_grid[::4]]} for day in timeline_days]
    greeks = position_greeks_at(request, request.underlying_price)["legs"]
    rng = np.random.default_rng(request.seed)
    days = max(maximum_days, 1)
    average_volatility = float(np.mean([leg.implied_volatility for leg in request.legs]))
    shocks = rng.normal((request.interest_rate - request.dividend_yield - average_volatility**2 / 2) / 365, average_volatility / np.sqrt(365), size=(request.paths, days))
    underlying_paths = request.underlying_price * np.exp(np.cumsum(shocks, axis=1))
    sample_days = np.linspace(0, days - 1, min(days, 90), dtype=int)
    samples = [{"path": path_number + 1, "points": [{"day": int(day + 1), "underlyingPrice": round(float(underlying_paths[path_number, day]), 2), "positionPnl": round(_position_pnl(request, float(underlying_paths[path_number, day]), int(day + 1)), 2)} for day in sample_days]} for path_number in range(min(request.paths, 20))]
    return {
        "model": "Cox-Ross-Rubinstein American Binomial",
        "comparisonModel": "Black-Scholes European",
        "historicalStatus": "Theoretical Simulation",
        "assumptions": {"interestRate": request.interest_rate, "dividendYield": request.dividend_yield, "valuationDate": date.today().isoformat(), "contractMultiplier": 100},
        "limitations": ["Yahoo provides current chains, not reliable historical contract marks.", "Probability estimates are model-based and are not forecasts.", "Taxes, pin risk, bid-ask depth, and broker margin rules are not modeled."],
        "positionProfile": position_profile(request),
        "conversionAnalysis": conversion_financing_analysis(request),
        "managementPlaybook": management_playbook(request),
        "dataProvenance": request.data_provenance,
        "summary": _summary(request, payoff),
        "greeks": greeks,
        "payoff": payoff,
        "surface": surface,
        "monteCarlo": samples,
    }
