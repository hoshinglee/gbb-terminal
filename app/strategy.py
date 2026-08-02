from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .indicators import IndicatorRegistry


@dataclass(frozen=True)
class StrategySpec:
    strategy_type: str
    name: str
    description: str
    direction: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Strategy(ABC):
    """Base contract for every strategy accepted by the backtest engine."""

    @property
    @abstractmethod
    def entry_criteria(self) -> str:
        pass

    @property
    @abstractmethod
    def exit_criteria(self) -> str:
        pass

    @abstractmethod
    def positions(self, history: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def spec(self) -> StrategySpec:
        pass

    @abstractmethod
    def to_yaml(self) -> str:
        pass


class DeclarativeStrategy(Strategy):
    """A safe Strategy subclass interpreted from validated YAML data."""

    def __init__(self, configuration: dict[str, Any]) -> None:
        self.configuration = StrategyFactory.validate(configuration)

    @property
    def entry_criteria(self) -> str:
        return _criteria_text(self.configuration["entry"])

    @property
    def exit_criteria(self) -> str:
        return _criteria_text(self.configuration["exit"])

    def positions(self, history: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(index=history.index)
        frame["close"] = history["Close"].astype(float)
        frame["volume"] = history["Volume"].fillna(0).astype(float) if "Volume" in history else 0.0
        for name, specification in self.configuration["indicators"].items():
            frame[name] = IndicatorRegistry.calculate(history, specification)
        entry_signal = _evaluate_criteria(self.configuration["entry"], frame)
        exit_signal = _evaluate_criteria(self.configuration["exit"], frame)
        active_value = 1 if self.configuration["direction"] == "long" else -1
        position, current = [], 0
        for enter, exit_trade in zip(entry_signal.fillna(False), exit_signal.fillna(False)):
            if current == 0 and bool(enter):
                current = active_value
            elif current != 0 and bool(exit_trade):
                current = 0
            position.append(current)
        frame["position"] = position
        return frame

    def spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_type="declarative",
            name=self.configuration["name"],
            description=self.configuration["description"],
            direction=self.configuration["direction"],
            parameters={
                "indicators": self.configuration["indicators"],
                "entry": self.configuration["entry"],
                "exit": self.configuration["exit"],
            },
        )

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.configuration, sort_keys=False)


class StrategyFactory:
    """Creates Strategy objects from YAML or legacy definitions without eval."""

    OPERATORS = {"crosses_above", "crosses_below", "greater_than", "less_than", "greater_or_equal", "less_or_equal"}

    @classmethod
    def from_yaml(cls, yaml_text: str) -> Strategy:
        try:
            configuration = yaml.safe_load(yaml_text)
        except yaml.YAMLError as error:
            raise ValueError(f"Strategy YAML is invalid: {error}") from error
        if not isinstance(configuration, dict):
            raise ValueError("Strategy YAML must contain a mapping at its root.")
        return DeclarativeStrategy(configuration)

    @classmethod
    def create(cls, definition: dict[str, Any]) -> Strategy:
        if "indicators" in definition:
            return DeclarativeStrategy(definition)
        parameters = definition.get("parameters", definition)
        fast_window = int(parameters["fast_window"])
        slow_window = int(parameters["slow_window"])
        if fast_window > slow_window:
            fast_window, slow_window = slow_window, fast_window
        return DeclarativeStrategy(moving_average_configuration(fast_window, slow_window, definition.get("direction", "long")))

    @classmethod
    def validate(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        required = {"version", "name", "description", "direction", "indicators", "entry", "exit"}
        missing = required - configuration.keys()
        if missing:
            raise ValueError(f"Strategy YAML is missing: {', '.join(sorted(missing))}.")
        if configuration["version"] != 1:
            raise ValueError("Only strategy YAML version 1 is supported.")
        if configuration["direction"] not in {"long", "short"}:
            raise ValueError("Strategy direction must be long or short.")
        if not isinstance(configuration["indicators"], dict) or not configuration["indicators"]:
            raise ValueError("A strategy must define at least one indicator.")
        for name, indicator in configuration["indicators"].items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError(f"Indicator alias '{name}' is invalid.")
            if not isinstance(indicator, dict) or indicator.get("type") not in IndicatorRegistry.DEFINITIONS:
                raise ValueError(f"Indicator '{name}' uses an unsupported type.")
        for section in ("entry", "exit"):
            _validate_criteria(configuration[section], set(configuration["indicators"]), cls.OPERATORS)
        return configuration


def moving_average_configuration(fast_window: int, slow_window: int, direction: str = "long") -> dict[str, Any]:
    if fast_window <= 0 or slow_window <= 0 or fast_window == slow_window:
        raise ValueError("Moving-average windows must be different positive numbers.")
    if direction not in {"long", "short"}:
        raise ValueError("Direction must be long or short.")
    entry_operator = "crosses_above" if direction == "long" else "crosses_below"
    exit_operator = "crosses_below" if direction == "long" else "crosses_above"
    return {
        "version": 1,
        "name": f"{direction.title()} MA{fast_window}/MA{slow_window} Crossover",
        "description": f"Enter {direction} when MA{fast_window} crosses its MA{slow_window} confirmation and exit on the reverse crossover.",
        "direction": direction,
        "indicators": {
            "fast_ma": {"type": "sma", "source": "close", "window": fast_window},
            "slow_ma": {"type": "sma", "source": "close", "window": slow_window},
        },
        "entry": {"all": [{"left": "fast_ma", "operator": entry_operator, "right": "slow_ma"}]},
        "exit": {"any": [{"left": "fast_ma", "operator": exit_operator, "right": "slow_ma"}]},
    }


def parse_strategy(instruction: str) -> Strategy:
    normalized = instruction.lower().replace("moving average", "ma")
    windows = [int(value) for value in re.findall(r"\bma\s*(\d+)\b", normalized)]
    if len(windows) < 2:
        raise ValueError("Include two moving averages, for example: MA5 crosses above MA10.")
    fast_window, slow_window = sorted(windows[:2])
    direction = "short" if re.search(r"\bshort\b", normalized) else "long"
    return DeclarativeStrategy(moving_average_configuration(fast_window, slow_window, direction))


def _validate_criteria(criteria: dict[str, Any], indicators: set[str], operators: set[str]) -> None:
    if not isinstance(criteria, dict) or len(criteria) != 1:
        raise ValueError("Criteria must contain exactly one 'all' or 'any' group.")
    group, rules = next(iter(criteria.items()))
    if group not in {"all", "any"} or not isinstance(rules, list) or not rules:
        raise ValueError("Criteria must contain a non-empty 'all' or 'any' rule list.")
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("left") not in indicators:
            raise ValueError("Every rule must reference a defined left indicator.")
        if rule.get("operator") not in operators:
            raise ValueError(f"Unsupported rule operator '{rule.get('operator')}'.")
        right = rule.get("right")
        if not isinstance(right, (int, float)) and right not in indicators:
            raise ValueError("Rule right-hand side must be a defined indicator or number.")


def _evaluate_criteria(criteria: dict[str, Any], frame: pd.DataFrame) -> pd.Series:
    group, rules = next(iter(criteria.items()))
    signals = [_evaluate_rule(rule, frame) for rule in rules]
    result = signals[0]
    for signal in signals[1:]:
        result = result & signal if group == "all" else result | signal
    return result


def _evaluate_rule(rule: dict[str, Any], frame: pd.DataFrame) -> pd.Series:
    left = frame[rule["left"]]
    right = frame[rule["right"]] if isinstance(rule["right"], str) else float(rule["right"])
    operator = rule["operator"]
    if operator == "crosses_above":
        return (left > right) & (left.shift(1) <= (right.shift(1) if isinstance(right, pd.Series) else right))
    if operator == "crosses_below":
        return (left < right) & (left.shift(1) >= (right.shift(1) if isinstance(right, pd.Series) else right))
    return {"greater_than": left > right, "less_than": left < right, "greater_or_equal": left >= right, "less_or_equal": left <= right}[operator]


def _criteria_text(criteria: dict[str, Any]) -> str:
    group, rules = next(iter(criteria.items()))
    joiner = " AND " if group == "all" else " OR "
    return joiner.join(f"{rule['left']} {rule['operator'].replace('_', ' ')} {rule['right']}" for rule in rules)


def _trades(frame: pd.DataFrame) -> list[dict[str, Any]]:
    trades, open_trade, previous_position = [], None, 0
    for index, row in frame.iterrows():
        position = int(row.position)
        if previous_position and position != previous_position and open_trade:
            multiplier, exit_price = (1 if previous_position == 1 else -1), float(row.close)
            pnl = (exit_price - open_trade["entryPrice"]) * multiplier
            trades.append({**open_trade, "exitDate": index.strftime("%Y-%m-%d"), "exitPrice": round(exit_price, 2), "pnl": round(pnl, 2), "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2)})
            open_trade = None
        if position and position != previous_position:
            open_trade = {"entryDate": index.strftime("%Y-%m-%d"), "entryPrice": round(float(row.close), 2), "side": "LONG" if position == 1 else "SHORT"}
        previous_position = position
    return trades


def run_backtest(history: pd.DataFrame, spy_history: pd.DataFrame, strategy: Strategy) -> dict[str, Any]:
    frame = strategy.positions(history)
    frame["position"] = frame["position"].shift(1).fillna(0)
    frame["daily_return"] = frame["close"].pct_change().fillna(0)
    frame["strategy_return"] = frame["position"] * frame["daily_return"]
    frame["equity"] = (1 + frame["strategy_return"]).cumprod()
    frame["benchmark_equity"] = (1 + frame["daily_return"]).cumprod()
    indicator_columns = list(strategy.spec().parameters["indicators"])
    active = frame.dropna(subset=indicator_columns).copy()
    if active.empty:
        raise ValueError("Not enough price history for the selected indicators.")
    spy = spy_history["Close"].dropna().astype(float).reindex(active.index).ffill().bfill()
    if spy.empty or spy.isna().any():
        raise ValueError("SPY history could not be aligned with the selected backtest window.")
    active["spy_equity"] = spy / float(spy.iloc[0])
    drawdown = active["equity"] / active["equity"].cummax() - 1
    annualized_volatility = active["strategy_return"].std() * np.sqrt(252)
    sharpe = 0.0 if annualized_volatility == 0 else active["strategy_return"].mean() * 252 / annualized_volatility
    trades = _trades(active)
    chart = [{"date": index.strftime("%Y-%m-%d"), "strategy": round(float(row.equity), 4), "buyHold": round(float(row.benchmark_equity), 4), "spy": round(float(row.spy_equity), 4), "volume": round(float(row.volume), 0)} for index, row in active.iterrows()]
    return {
        "strategy": strategy.spec().to_dict(), "strategyYaml": strategy.to_yaml(),
        "metrics": {"totalReturn": round((active.equity.iloc[-1] - 1) * 100, 2), "benchmarkReturn": round((active.benchmark_equity.iloc[-1] - 1) * 100, 2), "spyReturn": round((active.spy_equity.iloc[-1] - 1) * 100, 2), "maxDrawdown": round(drawdown.min() * 100, 2), "sharpeRatio": round(float(sharpe), 2), "trades": len(trades), "winRate": round(float(sum(trade["pnl"] > 0 for trade in trades) / len(trades) * 100), 1) if trades else 0.0},
        "chart": chart, "trades": trades,
    }


def monte_carlo(history: pd.DataFrame, days: int = 252, simulations: int = 400) -> dict[str, Any]:
    returns = history["Close"].pct_change().dropna().to_numpy()
    if len(returns) < 30:
        raise ValueError("Not enough history to run a simulation.")
    rng = np.random.default_rng(42)
    paths = np.cumprod(1 + rng.choice(returns, size=(simulations, days), replace=True), axis=1)
    final_returns, percentiles = (paths[:, -1] - 1) * 100, np.percentile(paths, [10, 50, 90], axis=0)
    chart_indices = np.linspace(0, days - 1, min(days, 100), dtype=int)
    return {"metrics": {"medianReturn": round(float(np.median(final_returns)), 2), "upsideReturn": round(float(np.percentile(final_returns, 90)), 2), "downsideReturn": round(float(np.percentile(final_returns, 10)), 2), "profitProbability": round(float((final_returns > 0).mean() * 100), 1)}, "paths": [{"day": int(index + 1), "p10": round(float(percentiles[0, index]), 4), "p50": round(float(percentiles[1, index]), 4), "p90": round(float(percentiles[2, index]), 4)} for index in chart_indices]}
