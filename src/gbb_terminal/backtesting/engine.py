from __future__ import annotations

from typing import Any

import pandas as pd

from ..strategy.factory import Strategy
from ..strategy.models import ExecutionAssumptions
from .execution import apply_execution
from .metrics import calculate_metrics, evidence_verdict, outcome_explanation, regime_analysis


def _trades(frame: pd.DataFrame) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None
    previous_position = 0
    for index, row in frame.iterrows():
        position = int(row.position)
        if previous_position and position != previous_position and open_trade:
            multiplier, exit_price = (1 if previous_position == 1 else -1), float(row.close)
            pnl = (exit_price - open_trade["entryPrice"]) * multiplier
            trades.append({**open_trade, "status": "Closed", "exitDate": index.strftime("%Y-%m-%d"), "exitPrice": round(exit_price, 2), "pnl": round(pnl, 2), "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2)})
            open_trade = None
        if position and position != previous_position:
            open_trade = {"entryDate": index.strftime("%Y-%m-%d"), "entryPrice": round(float(row.close), 2), "side": "LONG" if position == 1 else "SHORT"}
        previous_position = position
    if open_trade:
        final_index, final_price = frame.index[-1], float(frame.iloc[-1].close)
        multiplier = 1 if previous_position == 1 else -1
        pnl = (final_price - open_trade["entryPrice"]) * multiplier
        trades.append({**open_trade, "status": "Open", "exitDate": None, "exitPrice": round(final_price, 2), "asOfDate": final_index.strftime("%Y-%m-%d"), "pnl": round(pnl, 2), "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2)})
    return trades


def run_research_backtest(
    history: pd.DataFrame,
    benchmarks: dict[str, pd.DataFrame],
    strategy: Strategy,
    assumptions: ExecutionAssumptions | None = None,
) -> dict[str, Any]:
    assumptions = assumptions or ExecutionAssumptions()
    strategy_history = history.copy()
    if benchmarks:
        strategy_history["Benchmark_Close"] = next(iter(benchmarks.values()))["Close"].reindex(strategy_history.index).ffill().bfill()
    signal_frame = strategy.positions(strategy_history)
    frame = apply_execution(signal_frame, assumptions)
    indicator_columns = list(strategy.spec().parameters["indicators"])
    active = frame.dropna(subset=indicator_columns).copy()
    if active.empty:
        raise ValueError("Not enough price history for the selected indicators.")
    benchmark_columns = {"Buy & Hold": "benchmark_equity"}
    for label, benchmark_history in benchmarks.items():
        close = benchmark_history["Close"].dropna().astype(float).reindex(active.index).ffill().bfill()
        if close.empty or close.isna().any():
            raise ValueError(f"{label} history could not be aligned with the selected backtest window.")
        column = f"benchmark_{label.lower().replace(' ', '_').replace('&', 'and')}"
        active[column] = close / float(close.iloc[0])
        benchmark_columns[label] = column
    exposure = active["position"].abs()
    active["exposure_matched_equity"] = (1 + exposure * active["daily_return"]).cumprod()
    benchmark_columns["Exposure-Matched"] = "exposure_matched_equity"
    active["cash_equity"] = [(1 + assumptions.annual_cash_rate) ** (session / 252) for session in range(len(active))]
    benchmark_columns["Cash"] = "cash_equity"
    trades = _trades(active)
    metrics = calculate_metrics(active, trades, benchmark_columns)
    verdict = evidence_verdict(metrics)
    chart: list[dict[str, Any]] = []
    for index, row in active.iterrows():
        point: dict[str, Any] = {
            "date": index.strftime("%Y-%m-%d"),
            "strategy": round(float(row.equity), 4),
            "buyHold": round(float(row.benchmark_equity), 4),
            "spy": round(float(row.get("benchmark_spy", row.benchmark_equity)), 4),
            "open": round(float(history.loc[index, "Open"]), 4),
            "high": round(float(history.loc[index, "High"]), 4),
            "low": round(float(history.loc[index, "Low"]), 4),
            "close": round(float(row.close), 4),
            "volume": round(float(row.volume), 0),
            "position": int(row.position),
            "turnover": round(float(row.turnover), 4),
        }
        point["indicators"] = {column: round(float(row[column]), 4) for column in indicator_columns if pd.notna(row[column])}
        chart.append(point)
    return {
        "strategy": strategy.spec().to_dict(),
        "strategyYaml": strategy.to_yaml(),
        "metrics": metrics,
        "verdict": verdict,
        "explanation": outcome_explanation(metrics),
        "assumptions": assumptions.model_dump(mode="json"),
        "benchmarks": list(benchmark_columns),
        "regimes": regime_analysis(active, benchmark_columns.get("SPY", next(iter(benchmark_columns.values())))),
        "chart": chart,
        "trades": trades,
    }


def run_backtest(history: pd.DataFrame, spy_history: pd.DataFrame, strategy: Strategy) -> dict[str, Any]:
    return run_research_backtest(history, {"SPY": spy_history}, strategy)
