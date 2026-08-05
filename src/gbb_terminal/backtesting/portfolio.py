from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..strategy.models import StrategyInstance
from .metrics import drawdown_series, evidence_verdict, longest_underwater_days, outcome_explanation


def run_ranked_portfolio(
    histories: dict[str, pd.DataFrame],
    benchmark_history: pd.DataFrame,
    instance: StrategyInstance,
) -> dict[str, Any]:
    values = instance.parameter_values
    lookback = int(values["lookback_window"])
    top_n = int(values["top_n"])
    rebalance_sessions = int(values["rebalance_sessions"])
    if top_n > len(histories):
        raise ValueError("The number of holdings cannot exceed the supplied universe.")
    close = pd.concat({symbol: history["Close"].astype(float) for symbol, history in histories.items()}, axis=1).dropna()
    if len(close) <= lookback + rebalance_sessions:
        raise ValueError("The selected window is too short for this portfolio ranking design.")
    returns = close.pct_change().fillna(0)
    scores = close / close.shift(lookback) - 1
    target_weights = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    rebalance_rows: list[dict[str, Any]] = []
    for session in range(lookback, len(close), rebalance_sessions):
        ranked = scores.iloc[session].dropna().nlargest(top_n).index.tolist()
        target_weights.iloc[session] = 0.0
        target_weights.loc[close.index[session], ranked] = 1 / top_n
        rebalance_rows.append({"date": close.index[session].strftime("%Y-%m-%d"), "holdings": ranked, "scores": {symbol: round(float(scores.loc[close.index[session], symbol]) * 100, 2) for symbol in ranked}})
    weights = target_weights.ffill().fillna(0).shift(1).fillna(0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    costs = turnover * instance.execution.one_way_cost_rate
    portfolio_return = (weights * returns).sum(axis=1) - costs
    equity = (1 + portfolio_return).cumprod()
    buy_hold = (1 + returns.mean(axis=1)).cumprod()
    benchmark = benchmark_history["Close"].astype(float).reindex(close.index).ffill().bfill()
    benchmark_equity = benchmark / benchmark.iloc[0]
    years = max(len(close) / 252, 1 / 252)
    cagr = max(float(equity.iloc[-1]), 1e-9) ** (1 / years) - 1
    volatility = float(portfolio_return.std(ddof=0) * np.sqrt(252))
    sharpe = 0.0 if volatility == 0 else float(portfolio_return.mean() * 252 / volatility)
    downside = float(portfolio_return[portfolio_return < 0].std(ddof=0) * np.sqrt(252))
    sortino = 0.0 if downside == 0 or np.isnan(downside) else float(portfolio_return.mean() * 252 / downside)
    maximum_drawdown = abs(float(drawdown_series(equity).min()))
    benchmark_return = (float(buy_hold.iloc[-1]) - 1) * 100
    metrics = {
        "totalReturn": round((float(equity.iloc[-1]) - 1) * 100, 2),
        "benchmarkReturn": round(benchmark_return, 2),
        "spyReturn": round((float(benchmark_equity.iloc[-1]) - 1) * 100, 2),
        "benchmarkReturns": {"Equal-Weight Peers": round(benchmark_return, 2), instance.benchmark: round((float(benchmark_equity.iloc[-1]) - 1) * 100, 2)},
        "cagr": round(cagr * 100, 2),
        "excessReturn": round((float(equity.iloc[-1]) - float(buy_hold.iloc[-1])) * 100, 2),
        "sharpeRatio": round(sharpe, 2),
        "sortinoRatio": round(sortino, 2),
        "calmarRatio": round(cagr / maximum_drawdown, 2) if maximum_drawdown else 0.0,
        "maxDrawdown": round(-maximum_drawdown * 100, 2),
        "annualizedVolatility": round(volatility * 100, 2),
        "exposure": round(float(weights.abs().sum(axis=1).mean()) * 100, 1),
        "turnover": round(float(turnover.sum()), 2),
        "timeUnderwater": longest_underwater_days(equity),
        "trades": len(rebalance_rows),
        "openTrades": top_n,
        "winRate": 0.0,
        "profitFactor": None,
    }
    chart = [{"date": index.strftime("%Y-%m-%d"), "strategy": round(float(equity.loc[index]), 4), "buyHold": round(float(buy_hold.loc[index]), 4), "spy": round(float(benchmark_equity.loc[index]), 4), "position": round(float(weights.loc[index].abs().sum()), 2), "volume": 0, "close": round(float(close.loc[index].mean()), 4), "open": round(float(close.loc[index].mean()), 4), "high": round(float(close.loc[index].max()), 4), "low": round(float(close.loc[index].min()), 4), "turnover": round(float(turnover.loc[index]), 4), "indicators": {"holdings": ", ".join(weights.loc[index][weights.loc[index] > 0].index)}} for index in close.index]
    verdict = evidence_verdict(metrics)
    return {
        "strategy": {"strategy_type": "ranked_portfolio", "name": instance.name, "description": instance.description, "direction": "long", "parameters": instance.parameter_values},
        "metrics": metrics,
        "verdict": verdict,
        "explanation": outcome_explanation(metrics),
        "assumptions": instance.execution.model_dump(mode="json"),
        "benchmarks": ["Equal-Weight Peers", instance.benchmark],
        "chart": chart,
        "trades": [],
        "rebalances": rebalance_rows,
    }
