from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def longest_underwater_days(equity: pd.Series) -> int:
    underwater = drawdown_series(equity) < 0
    longest = current = 0
    for value in underwater:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def calculate_metrics(
    frame: pd.DataFrame,
    trades: list[dict[str, Any]],
    benchmark_columns: dict[str, str],
) -> dict[str, Any]:
    sessions = max(len(frame), 1)
    years = max(sessions / 252, 1 / 252)
    total_return = float(frame["equity"].iloc[-1] - 1)
    cagr = (max(float(frame["equity"].iloc[-1]), 1e-9) ** (1 / years)) - 1
    daily = frame["strategy_return"]
    annualized_volatility = float(daily.std(ddof=0) * np.sqrt(252))
    sharpe = 0.0 if annualized_volatility == 0 else float(daily.mean() * 252 / annualized_volatility)
    downside = float(daily[daily < 0].std(ddof=0) * np.sqrt(252))
    sortino = 0.0 if downside == 0 or np.isnan(downside) else float(daily.mean() * 252 / downside)
    drawdown = drawdown_series(frame["equity"])
    maximum_drawdown = abs(float(drawdown.min()))
    calmar = 0.0 if maximum_drawdown == 0 else cagr / maximum_drawdown
    closed = [trade for trade in trades if trade["status"] == "Closed"]
    wins = [float(trade["pnl"]) for trade in closed if trade["pnl"] > 0]
    losses = [abs(float(trade["pnl"])) for trade in closed if trade["pnl"] < 0]
    profit_factor = sum(wins) / sum(losses) if losses else (float("inf") if wins else 0.0)
    benchmarks = {
        label: round((float(frame[column].iloc[-1]) - 1) * 100, 2)
        for label, column in benchmark_columns.items()
        if column in frame
    }
    metrics: dict[str, Any] = {
        "totalReturn": round(total_return * 100, 2),
        "benchmarkReturn": benchmarks.get("Buy & Hold", 0.0),
        "spyReturn": benchmarks.get("SPY", 0.0),
        "benchmarkReturns": benchmarks,
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
    }
    return metrics


def evidence_verdict(metrics: dict[str, Any]) -> dict[str, str]:
    trades = int(metrics["trades"])
    excess = float(metrics["excessReturn"])
    sharpe = float(metrics["sharpeRatio"])
    calmar = float(metrics["calmarRatio"])
    if trades < 10:
        label = "Insufficient Evidence"
        reason = "The sample contains too few closed trades for a reliable conclusion."
    elif excess > 0 and sharpe >= 1 and calmar >= 0.75:
        label = "Robust Candidate"
        reason = "The strategy adds return with comparatively strong risk-adjusted evidence in this sample."
    elif sharpe > 0.5 and calmar > 0.3:
        label = "Promising But Unstable"
        reason = "Some risk-adjusted evidence is positive, but performance is not consistently compelling."
    else:
        label = "Does Not Justify Complexity"
        reason = "The tested rules do not improve enough on passive exposure after execution costs."
    return {"label": label, "reason": reason}


def outcome_explanation(metrics: dict[str, Any]) -> str:
    comparison = "outperformed" if metrics["excessReturn"] >= 0 else "underperformed"
    return (
        f"The strategy {comparison} buy-and-hold by {abs(metrics['excessReturn']):.2f}%, "
        f"with a maximum drawdown of {abs(metrics['maxDrawdown']):.2f}% and market exposure of "
        f"{metrics['exposure']:.1f}%."
    )

