from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategySpec:
    strategy_type: str
    name: str
    description: str
    direction: str
    parameters: dict[str, int | str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Strategy(ABC):
    """Base strategy contract used by every backtestable strategy."""

    @property
    @abstractmethod
    def entry_criteria(self) -> str:
        pass

    @property
    @abstractmethod
    def exit_criteria(self) -> str:
        pass

    @abstractmethod
    def positions(self, prices: pd.Series) -> pd.DataFrame:
        """Return price, indicators, and a position series (1, 0, or -1)."""

    @abstractmethod
    def spec(self) -> StrategySpec:
        pass


@dataclass(frozen=True)
class MovingAverageCrossoverStrategy(Strategy):
    fast_window: int
    slow_window: int
    direction: str = "long"

    @property
    def entry_criteria(self) -> str:
        relation = "above" if self.direction == "long" else "below"
        return f"Enter {self.direction} when MA{self.fast_window} crosses {relation} MA{self.slow_window}."

    @property
    def exit_criteria(self) -> str:
        relation = "below" if self.direction == "long" else "above"
        return f"Exit when MA{self.fast_window} crosses {relation} MA{self.slow_window}."

    def positions(self, prices: pd.Series) -> pd.DataFrame:
        frame = pd.DataFrame({"close": prices.astype(float)})
        frame["fast_ma"] = frame["close"].rolling(self.fast_window).mean()
        frame["slow_ma"] = frame["close"].rolling(self.slow_window).mean()
        active = (frame["fast_ma"] > frame["slow_ma"]).astype(int)
        frame["position"] = active if self.direction == "long" else -active
        return frame

    def spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_type="moving_average_crossover",
            name=f"{self.direction.title()} MA{self.fast_window}/MA{self.slow_window} Crossover",
            description=f"{self.entry_criteria} {self.exit_criteria}",
            direction=self.direction,
            parameters={"fast_window": self.fast_window, "slow_window": self.slow_window},
        )


class StrategyFactory:
    """Creates supported strategy implementations from validated definitions."""

    @staticmethod
    def create(definition: dict[str, Any]) -> Strategy:
        strategy_type = definition.get("strategy_type", "moving_average_crossover")
        if strategy_type != "moving_average_crossover":
            raise ValueError(f"Strategy type '{strategy_type}' is not supported yet.")
        parameters = definition.get("parameters", definition)
        fast_window = int(parameters["fast_window"])
        slow_window = int(parameters["slow_window"])
        direction = str(definition.get("direction", "long")).lower()
        if fast_window <= 0 or slow_window <= 0 or fast_window == slow_window:
            raise ValueError("Moving-average windows must be different positive numbers.")
        if direction not in {"long", "short"}:
            raise ValueError("Direction must be either long or short.")
        if fast_window > slow_window:
            fast_window, slow_window = slow_window, fast_window
        return MovingAverageCrossoverStrategy(fast_window, slow_window, direction)


def parse_strategy(instruction: str) -> Strategy:
    """Deterministic fallback for the MVP natural-language MA crossover syntax."""
    normalized = instruction.lower().replace("moving average", "ma")
    windows = [int(value) for value in re.findall(r"\bma\s*(\d+)\b", normalized)]
    if len(windows) < 2:
        raise ValueError("Include two moving averages, for example: MA5 crosses above MA10.")
    return StrategyFactory.create({
        "strategy_type": "moving_average_crossover",
        "parameters": {"fast_window": windows[0], "slow_window": windows[1]},
        "direction": "short" if re.search(r"\bshort\b", normalized) else "long",
    })


def _trades(frame: pd.DataFrame) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None
    previous_position = 0
    for index, row in frame.iterrows():
        position = int(row.position)
        if previous_position and position != previous_position and open_trade:
            multiplier = 1 if previous_position == 1 else -1
            exit_price = float(row.close)
            pnl = (exit_price - open_trade["entryPrice"]) * multiplier
            trades.append({
                **open_trade,
                "exitDate": index.strftime("%Y-%m-%d"),
                "exitPrice": round(exit_price, 2),
                "pnl": round(pnl, 2),
                "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2),
            })
            open_trade = None
        if position and position != previous_position:
            open_trade = {
                "entryDate": index.strftime("%Y-%m-%d"),
                "entryPrice": round(float(row.close), 2),
                "side": "LONG" if position == 1 else "SHORT",
            }
        previous_position = position
    return trades


def run_backtest(history: pd.DataFrame, spy_history: pd.DataFrame, strategy: Strategy) -> dict[str, Any]:
    frame = strategy.positions(history["Close"].dropna())
    frame["position"] = frame["position"].shift(1).fillna(0)
    frame["daily_return"] = frame["close"].pct_change().fillna(0)
    frame["strategy_return"] = frame["position"] * frame["daily_return"]
    frame["equity"] = (1 + frame["strategy_return"]).cumprod()
    frame["benchmark_equity"] = (1 + frame["daily_return"]).cumprod()
    active = frame.dropna(subset=["fast_ma", "slow_ma"]).copy()
    if active.empty:
        raise ValueError("Not enough price history for the selected moving averages.")
    spy = spy_history["Close"].dropna().astype(float).reindex(active.index).ffill().bfill()
    if spy.empty or spy.isna().any():
        raise ValueError("SPY history could not be aligned with the selected backtest window.")
    active["spy_equity"] = spy / float(spy.iloc[0])
    drawdown = active["equity"] / active["equity"].cummax() - 1
    annualized_volatility = active["strategy_return"].std() * np.sqrt(252)
    sharpe = 0.0 if annualized_volatility == 0 else active["strategy_return"].mean() * 252 / annualized_volatility
    trades = _trades(active)
    chart = [{
        "date": index.strftime("%Y-%m-%d"),
        "strategy": round(float(row.equity), 4),
        "buyHold": round(float(row.benchmark_equity), 4),
        "spy": round(float(row.spy_equity), 4),
    } for index, row in active.iterrows()]
    return {
        "strategy": strategy.spec().to_dict(),
        "metrics": {
            "totalReturn": round((active.equity.iloc[-1] - 1) * 100, 2),
            "benchmarkReturn": round((active.benchmark_equity.iloc[-1] - 1) * 100, 2),
            "spyReturn": round((active.spy_equity.iloc[-1] - 1) * 100, 2),
            "maxDrawdown": round(drawdown.min() * 100, 2),
            "sharpeRatio": round(float(sharpe), 2),
            "trades": len(trades),
            "winRate": round(float(sum(trade["pnl"] > 0 for trade in trades) / len(trades) * 100), 1) if trades else 0.0,
        },
        "chart": chart,
        "trades": trades,
    }


def monte_carlo(history: pd.DataFrame, days: int = 252, simulations: int = 400) -> dict[str, Any]:
    returns = history["Close"].pct_change().dropna().to_numpy()
    if len(returns) < 30:
        raise ValueError("Not enough history to run a simulation.")
    rng = np.random.default_rng(42)
    paths = np.cumprod(1 + rng.choice(returns, size=(simulations, days), replace=True), axis=1)
    final_returns = (paths[:, -1] - 1) * 100
    percentiles = np.percentile(paths, [10, 50, 90], axis=0)
    chart_indices = np.linspace(0, days - 1, min(days, 100), dtype=int)
    return {
        "metrics": {
            "medianReturn": round(float(np.median(final_returns)), 2),
            "upsideReturn": round(float(np.percentile(final_returns, 90)), 2),
            "downsideReturn": round(float(np.percentile(final_returns, 10)), 2),
            "profitProbability": round(float((final_returns > 0).mean() * 100), 1),
        },
        "paths": [{"day": int(index + 1), "p10": round(float(percentiles[0, index]), 4), "p50": round(float(percentiles[1, index]), 4), "p90": round(float(percentiles[2, index]), 4)} for index in chart_indices],
    }
