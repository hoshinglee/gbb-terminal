from __future__ import annotations

from typing import Any

import pandas as pd

from ..strategy.factory import Strategy
from ..strategy.models import ExecutionAssumptions
from .execution import apply_execution
from .metrics import EvidenceContext, calculate_metrics, evidence_verdict, outcome_explanation, regime_analysis


REQUIRED_PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _validated_history(history: pd.DataFrame, label: str) -> pd.DataFrame:
    if history.empty:
        raise ValueError(f"{label} history is empty.")
    missing = [column for column in REQUIRED_PRICE_COLUMNS if column not in history]
    if missing:
        raise ValueError(f"{label} history is missing: {', '.join(missing)}.")
    normalized = history.copy().sort_index()
    normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
    if normalized.index.has_duplicates:
        raise ValueError(f"{label} history contains duplicate sessions.")
    if normalized[["Open", "High", "Low", "Close"]].isna().any().any():
        raise ValueError(f"{label} history contains missing OHLC prices.")
    if (normalized[["Open", "High", "Low", "Close"]] <= 0).any().any():
        raise ValueError(f"{label} history contains non-positive OHLC prices.")
    if (normalized["High"] < normalized[["Open", "Close", "Low"]].max(axis=1)).any():
        raise ValueError(f"{label} history contains a high below another OHLC field.")
    if (normalized["Low"] > normalized[["Open", "Close", "High"]].min(axis=1)).any():
        raise ValueError(f"{label} history contains a low above another OHLC field.")
    if normalized["Volume"].fillna(0).lt(0).any():
        raise ValueError(f"{label} history contains negative volume.")
    return normalized


def _aligned_close(history: pd.DataFrame, index: pd.Index, label: str) -> pd.Series:
    close = history["Close"].astype(float).sort_index()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    aligned = close.reindex(index).ffill()
    if aligned.notna().sum() < 2:
        raise ValueError(f"{label} history could not be aligned with the selected backtest window.")
    return aligned


def _trades(frame: pd.DataFrame, assumptions: ExecutionAssumptions) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None
    previous_position = 0
    for index, row in frame.iterrows():
        position = int(row.position)
        if position == previous_position:
            continue
        fill_price = float(row.open)
        if previous_position and open_trade:
            entry_row = int(open_trade.pop("entryRow"))
            entry_equity = float(open_trade.pop("entryEquity"))
            exit_equity = float(row.equity)
            gross_return = (fill_price / open_trade["entryPrice"] - 1) * previous_position
            net_return = exit_equity / entry_equity - 1
            execution_cost = float(
                (
                    frame.iloc[entry_row : int(frame.index.get_loc(index)) + 1]["cost"]
                    * frame.iloc[entry_row : int(frame.index.get_loc(index)) + 1]["equity_before"]
                    * assumptions.initial_capital
                ).sum()
            )
            trades.append(
                {
                    **open_trade,
                    "status": "Closed",
                    "exitDate": index.strftime("%Y-%m-%d"),
                    "exitPrice": round(fill_price, 4),
                    "barsHeld": int(frame.index.get_loc(index) - entry_row),
                    "pnl": round(assumptions.initial_capital * (exit_equity - entry_equity), 2),
                    "pnlPercent": round(net_return * 100, 4),
                    "grossPnlPercent": round(gross_return * 100, 4),
                    "cost": round(execution_cost, 2),
                }
            )
            open_trade = None
        if position:
            open_trade = {
                "entryDate": index.strftime("%Y-%m-%d"),
                "entryPrice": round(fill_price, 4),
                "entryCapital": round(assumptions.initial_capital * float(row.equity_before), 2),
                "entryEquity": float(row.equity_before),
                "entryRow": int(frame.index.get_loc(index)),
                "side": "LONG" if position == 1 else "SHORT",
            }
        previous_position = position
    if open_trade:
        final_index, final_price = frame.index[-1], float(frame.iloc[-1].close)
        side = 1 if open_trade["side"] == "LONG" else -1
        gross_return = (final_price / open_trade["entryPrice"] - 1) * side
        entry_row = open_trade.pop("entryRow")
        entry_equity = float(open_trade.pop("entryEquity"))
        exit_equity = float(frame.iloc[-1].equity)
        net_return = exit_equity / entry_equity - 1
        execution_cost = float(
            (
                frame.iloc[entry_row:]["cost"]
                * frame.iloc[entry_row:]["equity_before"]
                * assumptions.initial_capital
            ).sum()
        )
        trades.append(
            {
                **open_trade,
                "status": "Open",
                "exitDate": None,
                "exitPrice": round(final_price, 4),
                "asOfDate": final_index.strftime("%Y-%m-%d"),
                "barsHeld": len(frame) - 1 - entry_row,
                "pnl": round(assumptions.initial_capital * (exit_equity - entry_equity), 2),
                "pnlPercent": round(net_return * 100, 4),
                "grossPnlPercent": round(gross_return * 100, 4),
                "cost": round(execution_cost, 2),
            }
        )
    return trades


def run_research_backtest(
    history: pd.DataFrame,
    benchmarks: dict[str, pd.DataFrame],
    strategy: Strategy,
    assumptions: ExecutionAssumptions | None = None,
    *,
    peer_histories: dict[str, pd.DataFrame] | None = None,
    evaluation_start: pd.Timestamp | str | None = None,
    evidence_context: EvidenceContext | None = None,
) -> dict[str, Any]:
    assumptions = assumptions or ExecutionAssumptions()
    strategy_history = _validated_history(history, "Underlying")
    normalized_benchmarks = {label: _validated_history(frame, label) for label, frame in benchmarks.items()}
    normalized_peers = {symbol: _validated_history(frame, symbol) for symbol, frame in (peer_histories or {}).items()}

    comparison_close: dict[str, pd.Series] = {
        label: _aligned_close(frame, strategy_history.index, label) for label, frame in normalized_benchmarks.items()
    }
    if comparison_close:
        strategy_history["Benchmark_Close"] = next(iter(comparison_close.values()))
    signal_frame = strategy.positions(strategy_history)
    indicator_columns = list(strategy.spec().parameters["indicators"])
    readiness = signal_frame[indicator_columns].notna().all(axis=1)
    for close in comparison_close.values():
        readiness &= close.notna()
    for symbol, peer_history in normalized_peers.items():
        readiness &= _aligned_close(peer_history, strategy_history.index, symbol).notna()
    if not readiness.any():
        raise ValueError("Not enough aligned price history for the selected indicators and benchmarks.")
    active_start = readiness[readiness].index[0]
    if evaluation_start is not None:
        requested_start = pd.Timestamp(evaluation_start).tz_localize(None)
        eligible = readiness.index[(readiness.index >= requested_start) & readiness]
        if eligible.empty:
            raise ValueError("The evaluation window starts after the available aligned history.")
        active_start = eligible[0]

    signal_frame.loc[signal_frame.index < active_start, "position"] = 0
    frame = apply_execution(signal_frame, assumptions)
    active = frame.loc[frame.index >= active_start].copy()
    if len(active) < 2:
        raise ValueError("The evaluation window requires at least two aligned sessions.")
    active.iloc[0, active.columns.get_loc("strategy_return")] = 0.0
    active.iloc[0, active.columns.get_loc("daily_return")] = 0.0
    active.iloc[0, active.columns.get_loc("turnover")] = 0.0
    active.iloc[0, active.columns.get_loc("cost")] = 0.0
    active["equity"] = (1 + active["strategy_return"]).cumprod()
    active["equity_before"] = active["equity"].shift(1).fillna(1.0)
    active["benchmark_equity"] = active["close"] / float(active["close"].iloc[0])

    benchmark_columns = {"Buy & Hold": "benchmark_equity"}
    for label, close in comparison_close.items():
        aligned = close.reindex(active.index).ffill()
        if aligned.isna().any():
            raise ValueError(f"{label} history has leading gaps in the evaluation window.")
        column = f"benchmark_{label.lower().replace(' ', '_').replace('&', 'and')}"
        active[column] = aligned / float(aligned.iloc[0])
        benchmark_columns[label] = column

    if normalized_peers:
        peer_returns = pd.concat(
            {
                symbol: _aligned_close(peer, active.index, symbol).pct_change()
                for symbol, peer in normalized_peers.items()
            },
            axis=1,
        ).mean(axis=1).fillna(0.0)
        active["equal_weight_peers_equity"] = (1 + peer_returns).cumprod()
        benchmark_columns["Equal-Weight Peers"] = "equal_weight_peers_equity"

    exposure = active["position"].abs()
    active["exposure_matched_equity"] = (1 + exposure * active["daily_return"]).cumprod()
    benchmark_columns["Exposure-Matched"] = "exposure_matched_equity"
    underlying_volatility = float(active["daily_return"].std(ddof=0))
    strategy_volatility = float(active["strategy_return"].std(ddof=0))
    volatility_scale = min(strategy_volatility / underlying_volatility, 2.0) if underlying_volatility > 0 else 0.0
    active["volatility_matched_equity"] = (1 + active["daily_return"] * volatility_scale).cumprod()
    benchmark_columns["Volatility-Matched"] = "volatility_matched_equity"
    cash_daily_rate = (1 + assumptions.annual_cash_rate) ** (1 / 252) - 1
    active["cash_equity"] = (1 + pd.Series(cash_daily_rate, index=active.index)).cumprod()
    active["cash_equity"] /= float(active["cash_equity"].iloc[0])
    benchmark_columns["Cash"] = "cash_equity"

    trades = _trades(active, assumptions)
    metrics = calculate_metrics(active, trades, benchmark_columns, assumptions)
    verdict = evidence_verdict(metrics, evidence_context)
    chart: list[dict[str, Any]] = []
    for index, row in active.iterrows():
        benchmark_values = {label: round(float(row[column]), 4) for label, column in benchmark_columns.items()}
        point: dict[str, Any] = {
            "date": index.strftime("%Y-%m-%d"),
            "strategy": round(float(row.equity), 4),
            "buyHold": benchmark_values["Buy & Hold"],
            "spy": benchmark_values.get("SPY", benchmark_values["Buy & Hold"]),
            "benchmarks": benchmark_values,
            "open": round(float(row.open), 4),
            "high": round(float(row.high), 4),
            "low": round(float(row.low), 4),
            "close": round(float(row.close), 4),
            "volume": round(float(row.volume), 0),
            "signalPosition": int(row.signal_position),
            "position": int(row.position),
            "fillPrice": round(float(row.fill_price), 4) if pd.notna(row.fill_price) else None,
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
        "executionModel": "Signals observed at session close; target positions fill at the next session open.",
        "evaluationPeriod": {
            "start": active.index[0].strftime("%Y-%m-%d"),
            "end": active.index[-1].strftime("%Y-%m-%d"),
            "sessions": len(active),
        },
        "benchmarks": list(benchmark_columns),
        "regimes": regime_analysis(active, benchmark_columns.get("SPY", benchmark_columns["Buy & Hold"])),
        "chart": chart,
        "trades": trades,
        "qualityWarnings": ["Strategy equity was depleted during the evaluation window."] if bool(active["insolvent"].any()) else [],
    }


def run_backtest(history: pd.DataFrame, spy_history: pd.DataFrame, strategy: Strategy) -> dict[str, Any]:
    return run_research_backtest(history, {"SPY": spy_history}, strategy)
