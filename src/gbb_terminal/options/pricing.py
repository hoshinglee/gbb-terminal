from __future__ import annotations

from math import erf, exp, log, sqrt

import numpy as np

from .models import OptionType


def _intrinsic(option_type: OptionType, spot: float, strike: float) -> float:
    return max(spot - strike, 0.0) if option_type == OptionType.CALL else max(strike - spot, 0.0)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + erf(value / sqrt(2)))


def black_scholes_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    years: float,
    volatility: float,
    interest_rate: float,
    dividend_yield: float = 0.0,
) -> float:
    if years <= 0:
        return _intrinsic(option_type, spot, strike)
    sigma_root = volatility * sqrt(years)
    if sigma_root <= 0:
        return _intrinsic(option_type, spot, strike)
    first = (log(spot / strike) + (interest_rate - dividend_yield + volatility**2 / 2) * years) / sigma_root
    second = first - sigma_root
    if option_type == OptionType.CALL:
        return spot * exp(-dividend_yield * years) * _normal_cdf(first) - strike * exp(-interest_rate * years) * _normal_cdf(second)
    return strike * exp(-interest_rate * years) * _normal_cdf(-second) - spot * exp(-dividend_yield * years) * _normal_cdf(-first)


def american_option_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    years: float,
    volatility: float,
    interest_rate: float,
    dividend_yield: float = 0.0,
    steps: int = 150,
) -> float:
    if years <= 0:
        return _intrinsic(option_type, spot, strike)
    steps = max(25, min(steps, 500))
    delta_time = years / steps
    up = exp(volatility * sqrt(delta_time))
    down = 1 / up
    discount = exp(-interest_rate * delta_time)
    probability = (exp((interest_rate - dividend_yield) * delta_time) - down) / (up - down)
    probability = min(max(probability, 0.0), 1.0)
    nodes = np.arange(steps + 1)
    spots = spot * up ** (steps - nodes) * down**nodes
    if option_type == OptionType.CALL:
        values = np.maximum(spots - strike, 0.0)
    else:
        values = np.maximum(strike - spots, 0.0)
    for step in range(steps - 1, -1, -1):
        values = discount * (probability * values[:-1] + (1 - probability) * values[1:])
        nodes = np.arange(step + 1)
        spots = spot * up ** (step - nodes) * down**nodes
        exercise = np.maximum(spots - strike, 0.0) if option_type == OptionType.CALL else np.maximum(strike - spots, 0.0)
        values = np.maximum(values, exercise)
    return float(values[0])


def option_greeks(
    option_type: OptionType,
    spot: float,
    strike: float,
    years: float,
    volatility: float,
    interest_rate: float,
    dividend_yield: float = 0.0,
) -> dict[str, float]:
    price = american_option_price(option_type, spot, strike, years, volatility, interest_rate, dividend_yield)
    spot_step = max(spot * 0.005, 0.01)
    volatility_step = 0.01
    day = min(1 / 365, max(years, 1 / 365))
    up = american_option_price(option_type, spot + spot_step, strike, years, volatility, interest_rate, dividend_yield)
    down = american_option_price(option_type, max(spot - spot_step, 0.01), strike, years, volatility, interest_rate, dividend_yield)
    higher_volatility = american_option_price(option_type, spot, strike, years, volatility + volatility_step, interest_rate, dividend_yield)
    tomorrow = american_option_price(option_type, spot, strike, max(years - day, 0), volatility, interest_rate, dividend_yield)
    return {
        "price": round(price, 4),
        "delta": round((up - down) / (2 * spot_step), 4),
        "gamma": round((up - 2 * price + down) / spot_step**2, 6),
        "theta": round(tomorrow - price, 4),
        "vega": round(higher_volatility - price, 4),
    }


def probability_in_the_money(option_type: OptionType, spot: float, strike: float, years: float, volatility: float, interest_rate: float, dividend_yield: float = 0.0) -> float:
    if years <= 0:
        return float(_intrinsic(option_type, spot, strike) > 0)
    second = (log(spot / strike) + (interest_rate - dividend_yield - volatility**2 / 2) * years) / (volatility * sqrt(years))
    return _normal_cdf(second) if option_type == OptionType.CALL else _normal_cdf(-second)

