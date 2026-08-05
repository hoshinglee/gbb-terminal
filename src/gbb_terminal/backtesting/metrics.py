from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..strategy.models import ExecutionAssumptions


@dataclass(frozen=True)
class EvidenceContext:
    out_of_sample: bool = False
    stable_parameters: bool = False
    deflated_sharpe_probability: float = 0.0
    walk_forward_folds: int = 0


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def longest_underwater_days(equity: pd.Series) -> int:
    underwater = drawdown_series(equity) < 0
    longest = current = 0
    for value in underwater:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _years(index: pd.Index) -> float:
    if len(index) < 2:
        return 1 / 252
    calendar_days = max((pd.Timestamp(index[-1]) - pd.Timestamp(index[0])).days, 1)
    return max(calendar_days / 365.25, 1 / 252)


def _series_metrics(equity: pd.Series, years: float) -> dict[str, float]:
    ending = max(float(equity.iloc[-1]), 1e-12)
    returns = equity.pct_change().fillna(0.0)
    drawdown = drawdown_series(equity)
    return {
        "totalReturn": round((ending - 1) * 100, 2),
        "cagr": round((ending ** (1 / years) - 1) * 100, 2),
        "maxDrawdown": round(float(drawdown.min()) * 100, 2),
        "annualizedVolatility": round(float(returns.std(ddof=0) * np.sqrt(252)) * 100, 2),
    }


def calculate_metrics(
    frame: pd.DataFrame,
    trades: list[dict[str, Any]],
    benchmark_columns: dict[str, str],
    assumptions: ExecutionAssumptions | None = None,
) -> dict[str, Any]:
    assumptions = assumptions or ExecutionAssumptions()
    years = _years(frame.index)
    total_return = float(frame["equity"].iloc[-1] - 1)
    cagr = max(float(frame["equity"].iloc[-1]), 1e-12) ** (1 / years) - 1
    daily = frame["strategy_return"]
    cash_daily_rate = (1 + assumptions.annual_cash_rate) ** (1 / 252) - 1
    excess_daily = daily - cash_daily_rate
    annualized_volatility = float(daily.std(ddof=0) * np.sqrt(252))
    sharpe = 0.0 if annualized_volatility == 0 else float(excess_daily.mean() * 252 / annualized_volatility)
    downside = float(excess_daily[excess_daily < 0].std(ddof=0) * np.sqrt(252))
    sortino = 0.0 if downside == 0 or np.isnan(downside) else float(excess_daily.mean() * 252 / downside)
    drawdown = drawdown_series(frame["equity"])
    maximum_drawdown = abs(float(drawdown.min()))
    calmar = 0.0 if maximum_drawdown == 0 else cagr / maximum_drawdown
    closed = [trade for trade in trades if trade["status"] == "Closed"]
    wins = [float(trade["pnl"]) for trade in closed if trade["pnl"] > 0]
    losses = [abs(float(trade["pnl"])) for trade in closed if trade["pnl"] < 0]
    profit_factor = sum(wins) / sum(losses) if losses else (float("inf") if wins else 0.0)
    benchmark_metrics = {
        label: _series_metrics(frame[column], years)
        for label, column in benchmark_columns.items()
        if column in frame
    }
    benchmarks = {label: values["totalReturn"] for label, values in benchmark_metrics.items()}
    total_cost = float((frame["cost"] * frame["equity_before"] * assumptions.initial_capital).sum())
    metrics: dict[str, Any] = {
        "totalReturn": round(total_return * 100, 2),
        "benchmarkReturn": benchmarks.get("Buy & Hold", 0.0),
        "spyReturn": benchmarks.get("SPY", 0.0),
        "benchmarkReturns": benchmarks,
        "benchmarkMetrics": benchmark_metrics,
        "excessReturns": {label: round(total_return * 100 - value, 2) for label, value in benchmarks.items()},
        "cagr": round(cagr * 100, 2),
        "excessReturn": round(total_return * 100 - benchmarks.get("Buy & Hold", 0.0), 2),
        "sharpeRatio": round(sharpe, 2),
        "sortinoRatio": round(sortino, 2),
        "calmarRatio": round(calmar, 2),
        "maxDrawdown": round(-maximum_drawdown * 100, 2),
        "annualizedVolatility": round(annualized_volatility * 100, 2),
        "exposure": round(float(frame["position"].abs().mean()) * 100, 1),
        "turnover": round(float(frame["turnover"].sum()), 2),
        "timeUnderwater": longest_underwater_days(frame["equity"]),
        "trades": len(closed),
        "openTrades": len(trades) - len(closed),
        "winRate": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
        "profitFactor": None if np.isinf(profit_factor) else round(profit_factor, 2),
        "averageTradePnl": round(float(np.mean([trade["pnl"] for trade in closed])), 2) if closed else 0.0,
        "averageTradeReturn": round(float(np.mean([trade["pnlPercent"] for trade in closed])), 2) if closed else 0.0,
        "endingCapital": round(assumptions.initial_capital * float(frame["equity"].iloc[-1]), 2),
        "totalExecutionCosts": round(total_cost, 2),
        "costSensitivity": [
            {
                "totalCostBps": basis_points,
                "totalReturn": round(
                    ((1 + (frame["strategy_return"] + frame["cost"] - frame["turnover"] * basis_points / 10_000)).cumprod().iloc[-1] - 1) * 100,
                    2,
                ),
            }
            for basis_points in (0, 3, 5, 10, 25)
        ],
    }
    return metrics


def regime_analysis(frame: pd.DataFrame, benchmark_column: str) -> list[dict[str, Any]]:
    benchmark_returns = frame[benchmark_column].pct_change().fillna(0)
    trend = frame[benchmark_column].rolling(50).mean() >= frame[benchmark_column].rolling(200).mean()
    volatility = benchmark_returns.rolling(20).std(ddof=0) * np.sqrt(252)
    high_volatility = volatility >= volatility.median()
    regimes = pd.Series("Transition", index=frame.index)
    regimes[trend & ~high_volatility] = "Bull / Lower Volatility"
    regimes[trend & high_volatility] = "Bull / Higher Volatility"
    regimes[~trend & ~high_volatility] = "Bear / Lower Volatility"
    regimes[~trend & high_volatility] = "Bear / Higher Volatility"
    results = []
    for regime, segment in frame.groupby(regimes):
        if len(segment) < 5:
            continue
        results.append(
            {
                "regime": regime,
                "sessions": len(segment),
                "strategyReturn": round(((1 + segment["strategy_return"]).prod() - 1) * 100, 2),
                "averageExposure": round(float(segment["position"].abs().mean()) * 100, 1),
            }
        )
    return results


def evidence_verdict(metrics: dict[str, Any], context: EvidenceContext | None = None) -> dict[str, str]:
    context = context or EvidenceContext()
    trades = int(metrics["trades"])
    excess = float(metrics["excessReturn"])
    sharpe = float(metrics["sharpeRatio"])
    calmar = float(metrics["calmarRatio"])
    if trades < 10:
        label = "Insufficient Evidence"
        reason = "The sample contains fewer than ten closed trades, so the result cannot support a reliable conclusion."
    elif context.out_of_sample and context.stable_parameters and context.deflated_sharpe_probability >= 0.8 and excess > 0 and sharpe >= 1 and calmar >= 0.75:
        label = "Robust Candidate"
        reason = "Untouched holdout performance is positive, nearby parameters are stable, and selection-adjusted evidence is comparatively strong."
    elif sharpe > 0.5 and calmar > 0.3:
        label = "Promising But Unstable"
        reason = "Risk-adjusted performance is positive, but the evidence is not yet both stable and independently confirmed out of sample."
    else:
        label = "Does Not Justify Complexity"
        reason = "The tested rules do not improve enough on passive exposure after execution costs."
    return {"label": label, "reason": reason}


def outcome_explanation(metrics: dict[str, Any]) -> str:
    comparison = "outperformed" if metrics["excessReturn"] >= 0 else "underperformed"
    buy_hold_drawdown = abs(float(metrics.get("benchmarkMetrics", {}).get("Buy & Hold", {}).get("maxDrawdown", 0.0)))
    return (
        f"The strategy {comparison} buy-and-hold by {abs(metrics['excessReturn']):.2f}%, "
        f"with maximum drawdown of {abs(metrics['maxDrawdown']):.2f}% versus {buy_hold_drawdown:.2f}% for buy-and-hold, "
        f"while invested {metrics['exposure']:.1f}% of sessions."
    )
