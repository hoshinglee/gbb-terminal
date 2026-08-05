from __future__ import annotations

import pandas as pd
import pytest

from gbb_terminal.backtesting.engine import run_research_backtest
from gbb_terminal.backtesting.execution import apply_execution
from gbb_terminal.strategy.catalogue import catalogue
from gbb_terminal.strategy.models import ExecutionAssumptions


def test_close_signal_fills_next_open_without_capturing_pre_fill_gap():
    index = pd.bdate_range("2024-01-02", periods=4)
    frame = pd.DataFrame(
        {
            "open": [100.0, 110.0, 120.0, 90.0],
            "close": [100.0, 115.0, 100.0, 95.0],
            "position": [1, 1, 0, 0],
        },
        index=index,
    )

    executed = apply_execution(frame, ExecutionAssumptions(commission_bps=0, slippage_bps=0))

    assert executed.loc[index[0], "position"] == 0
    assert executed.loc[index[1], "position"] == 1
    assert executed.loc[index[1], "fill_price"] == 110
    assert executed.loc[index[1], "strategy_return"] == pytest.approx(115 / 110 - 1)
    assert executed.loc[index[2], "strategy_return"] == pytest.approx(100 / 115 - 1)
    assert executed.loc[index[3], "position"] == 0
    assert executed.loc[index[3], "strategy_return"] == pytest.approx(90 / 100 - 1)


def test_trade_ledger_uses_next_open_fill_prices(price_history, benchmark_history):
    instance = catalogue.create_instance(
        "sma-crossover",
        {"fast_window": 5, "slow_window": 20},
        ticker="AAPL",
        execution=ExecutionAssumptions(commission_bps=1, slippage_bps=2),
    )
    result = run_research_backtest(price_history, {"SPY": benchmark_history}, catalogue.build(instance), instance.execution)
    fills = {point["date"]: point["fillPrice"] for point in result["chart"] if point["fillPrice"] is not None}

    assert result["trades"]
    for trade in result["trades"]:
        assert trade["entryPrice"] == fills[trade["entryDate"]]
        if trade["status"] == "Closed":
            assert trade["exitPrice"] == fills[trade["exitDate"]]
        assert "entryRow" not in trade
        assert trade["pnl"] == pytest.approx(trade["entryCapital"] * trade["pnlPercent"] / 100, abs=1.0)


def test_benchmark_alignment_never_backfills_future_prices(price_history, benchmark_history):
    delayed_benchmark = benchmark_history.iloc[120:]
    instance = catalogue.create_instance("sma-crossover", {"fast_window": 5, "slow_window": 20}, ticker="AAPL")

    result = run_research_backtest(price_history, {"SPY": delayed_benchmark}, catalogue.build(instance))

    assert result["evaluationPeriod"]["start"] >= delayed_benchmark.index[0].strftime("%Y-%m-%d")
    assert result["chart"][0]["spy"] == 1.0
    assert result["chart"][0]["buyHold"] == 1.0
    assert result["chart"][0]["strategy"] == 1.0


def test_metrics_include_reproducible_execution_and_benchmark_evidence(price_history, benchmark_history):
    sector = benchmark_history.copy()
    sector["Close"] *= 1.001
    peer = price_history.copy()
    peer["Close"] *= 0.997
    instance = catalogue.create_instance("rsi-mean-reversion", ticker="AAPL", benchmark="SPY")

    result = run_research_backtest(
        price_history,
        {"SPY": benchmark_history, "XLK": sector},
        catalogue.build(instance),
        instance.execution,
        peer_histories={"MSFT": peer},
    )

    expected = {"Buy & Hold", "SPY", "XLK", "Equal-Weight Peers", "Exposure-Matched", "Volatility-Matched", "Cash"}
    assert expected <= set(result["metrics"]["benchmarkMetrics"])
    assert result["assumptions"]["fill_price"] == "next_open"
    assert result["assumptions"]["signal_lag_sessions"] == 1
    assert result["executionModel"].endswith("next session open.")
