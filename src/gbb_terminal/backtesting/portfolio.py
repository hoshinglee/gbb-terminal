from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..strategy.models import ExecutionAssumptions, StrategyInstance
from .metrics import calculate_metrics, evidence_verdict, regime_analysis


def run_ranked_portfolio(
    histories: dict[str, pd.DataFrame],
    benchmark_history: pd.DataFrame,
    instance: StrategyInstance,
    assumptions: ExecutionAssumptions | None = None,
    benchmark_symbol: str = "SPY",
) -> dict[str, Any]:
    assumptions = assumptions or ExecutionAssumptions()
    values = instance.parameter_values
    lookback = int(values["lookback_window"])
    top_n = int(values["top_n"])
    rebalance_sessions = int(values["rebalance_sessions"])
    if top_n > len(histories):
        raise ValueError("The number of holdings cannot exceed the supplied universe.")
    close = pd.concat({symbol: history["Close"].astype(float) for symbol, history in histories.items()}, axis=1).dropna()
    open_price = pd.concat({symbol: history["Open"].astype(float) for symbol, history in histories.items()}, axis=1).reindex(close.index)
    if open_price.isna().any().any() or (open_price <= 0).any().any() or (close <= 0).any().any():
        raise ValueError("Portfolio histories require aligned positive open and close prices.")
    benchmark = benchmark_history["Close"].astype(float).sort_index().reindex(close.index).ffill()
    first_benchmark = benchmark.first_valid_index()
    if first_benchmark is None:
        raise ValueError("Benchmark history does not overlap the portfolio universe.")
    close = close.loc[close.index >= first_benchmark]
    open_price = open_price.reindex(close.index)
    benchmark = benchmark.reindex(close.index)
    if len(close) <= lookback + rebalance_sessions:
        raise ValueError("The selected window is too short for this portfolio ranking design.")

    scores = close / close.shift(lookback) - 1
    target_weights = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    rebalance_rows: list[dict[str, Any]] = []
    for signal_session in range(lookback, len(close) - 1, rebalance_sessions):
        ranked = scores.iloc[signal_session].dropna().nlargest(top_n).index.tolist()
        target_weights.iloc[signal_session] = 0.0
        target_weights.loc[close.index[signal_session], ranked] = 1 / top_n
        rebalance_rows.append(
            {
                "signalDate": close.index[signal_session].strftime("%Y-%m-%d"),
                "executionDate": close.index[signal_session + 1].strftime("%Y-%m-%d"),
                "holdings": ranked,
                "scores": {
                    symbol: round(float(scores.loc[close.index[signal_session], symbol]) * 100, 2)
                    for symbol in ranked
                },
            }
        )

    weights = target_weights.ffill().fillna(0.0).shift(assumptions.signal_lag_sessions).fillna(0.0)
    previous_weights = weights.shift(1).fillna(0.0)
    overnight_returns = (open_price / close.shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    intraday_returns = (close / open_price - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    overnight_portfolio_return = (previous_weights * overnight_returns).sum(axis=1)
    intraday_portfolio_return = (weights * intraday_returns).sum(axis=1)
    gross_return = (1 + overnight_portfolio_return) * (1 + intraday_portfolio_return) - 1
    turnover = (weights - previous_weights).abs().sum(axis=1)
    costs = turnover * assumptions.one_way_cost_rate
    cash_daily_rate = (1 + assumptions.annual_cash_rate) ** (1 / 252) - 1
    cash_return = ((previous_weights.abs().sum(axis=1) == 0) & (weights.abs().sum(axis=1) == 0)).astype(float) * cash_daily_rate
    portfolio_return = (1 + gross_return + cash_return - costs).clip(lower=1e-9) - 1

    active_start = close.index[lookback]
    active = pd.DataFrame(index=close.loc[close.index >= active_start].index)
    active["strategy_return"] = portfolio_return.reindex(active.index)
    active.iloc[0, active.columns.get_loc("strategy_return")] = 0.0
    active["equity"] = (1 + active["strategy_return"]).cumprod()
    active["equity_before"] = active["equity"].shift(1).fillna(1.0)
    active["position"] = weights.abs().sum(axis=1).reindex(active.index)
    active["turnover"] = turnover.reindex(active.index)
    active.iloc[0, active.columns.get_loc("turnover")] = 0.0
    active["cost"] = costs.reindex(active.index)
    active.iloc[0, active.columns.get_loc("cost")] = 0.0

    equal_weight_returns = close.pct_change().mean(axis=1).fillna(0.0).reindex(active.index)
    equal_weight_returns.iloc[0] = 0.0
    active["daily_return"] = equal_weight_returns
    active["equal_weight_peers"] = (1 + equal_weight_returns).cumprod()
    benchmark_close = benchmark.reindex(active.index)
    active["selected_benchmark"] = benchmark_close / float(benchmark_close.iloc[0])
    active["exposure_matched_equity"] = (1 + active["position"] * equal_weight_returns).cumprod()
    peer_volatility = float(equal_weight_returns.std(ddof=0))
    strategy_volatility = float(active["strategy_return"].std(ddof=0))
    volatility_scale = min(strategy_volatility / peer_volatility, 2.0) if peer_volatility > 0 else 0.0
    active["volatility_matched_equity"] = (1 + equal_weight_returns * volatility_scale).cumprod()
    active["cash_equity"] = (1 + pd.Series(cash_daily_rate, index=active.index)).cumprod()
    active["cash_equity"] /= float(active["cash_equity"].iloc[0])
    benchmark_columns = {
        "Equal-Weight Peers": "equal_weight_peers",
        benchmark_symbol: "selected_benchmark",
        "Exposure-Matched": "exposure_matched_equity",
        "Volatility-Matched": "volatility_matched_equity",
        "Cash": "cash_equity",
    }
    metrics = calculate_metrics(active, [], benchmark_columns, assumptions)
    metrics["benchmarkReturn"] = metrics["benchmarkReturns"]["Equal-Weight Peers"]
    metrics["excessReturn"] = metrics["excessReturns"]["Equal-Weight Peers"]
    metrics["trades"] = len(rebalance_rows)
    metrics["openTrades"] = top_n
    verdict = evidence_verdict(metrics)
    comparison = "outperformed" if metrics["excessReturn"] >= 0 else "underperformed"
    portfolio_explanation = (
        f"The ranked portfolio {comparison} equal-weight peers by {abs(metrics['excessReturn']):.2f}%, "
        f"with maximum drawdown of {abs(metrics['maxDrawdown']):.2f}% and average gross exposure of "
        f"{metrics['exposure']:.1f}%."
    )

    active_close = close.reindex(active.index)
    active_weights = weights.reindex(active.index)
    chart = [
        {
            "date": index.strftime("%Y-%m-%d"),
            "strategy": round(float(active.loc[index, "equity"]), 4),
            "buyHold": round(float(active.loc[index, "equal_weight_peers"]), 4),
            "spy": round(float(active.loc[index, "selected_benchmark"]), 4),
            "benchmarks": {label: round(float(active.loc[index, column]), 4) for label, column in benchmark_columns.items()},
            "signalPosition": round(float(target_weights.ffill().fillna(0.0).loc[index].abs().sum()), 2),
            "position": round(float(active.loc[index, "position"]), 2),
            "volume": 0,
            "close": round(float(active_close.loc[index].mean()), 4),
            "open": round(float(open_price.loc[index].mean()), 4),
            "high": round(float(active_close.loc[index].max()), 4),
            "low": round(float(active_close.loc[index].min()), 4),
            "fillPrice": None,
            "turnover": round(float(active.loc[index, "turnover"]), 4),
            "indicators": {"holdings": ", ".join(active_weights.loc[index][active_weights.loc[index] > 0].index)},
        }
        for index in active.index
    ]
    return {
        "strategy": {
            "strategy_type": "ranked_portfolio",
            "name": instance.name,
            "description": instance.description,
            "direction": "long",
            "parameters": instance.parameter_values,
        },
        "metrics": metrics,
        "verdict": verdict,
        "explanation": portfolio_explanation,
        "assumptions": assumptions.model_dump(mode="json"),
        "executionModel": "Rankings observed at session close; portfolio rebalances fill at the next session open.",
        "evaluationPeriod": {
            "start": active.index[0].strftime("%Y-%m-%d"),
            "end": active.index[-1].strftime("%Y-%m-%d"),
            "sessions": len(active),
        },
        "benchmarks": list(benchmark_columns),
        "regimes": regime_analysis(active, "selected_benchmark"),
        "chart": chart,
        "trades": [],
        "rebalances": rebalance_rows,
    }
