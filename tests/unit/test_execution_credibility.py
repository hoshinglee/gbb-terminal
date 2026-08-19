from __future__ import annotations

import pandas as pd
import pytest

from gbb_terminal.backtesting.engine import run_research_backtest
from gbb_terminal.backtesting.execution import apply_execution
from gbb_terminal.strategy.catalogue import catalogue
from gbb_terminal.strategy.factory import StrategyFactory, StrategySpec
from gbb_terminal.strategy.models import ExecutionAssumptions


class AlwaysLongStrategy:
    def positions(self, history):
        frame = pd.DataFrame(index=history.index)
        frame["open"] = history["Open"]
        frame["high"] = history["High"]
        frame["low"] = history["Low"]
        frame["close"] = history["Close"]
        frame["volume"] = history["Volume"]
        frame["position"] = 1
        return frame

    def spec(self):
        return StrategySpec("test", "Always Long", "Remain invested after next-open execution.", "long", {"indicators": {}})

    def to_yaml(self):
        return "version: 1\n"


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
    result = run_research_backtest(price_history, {"SPY": benchmark_history}, catalogue.build(instance), ExecutionAssumptions(commission_bps=1, slippage_bps=2))
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
        ExecutionAssumptions(),
        peer_histories={"MSFT": peer},
    )

    expected = {"Buy & Hold", "Next-Open Buy & Hold", "SPY", "XLK", "Equal-Weight Peers", "Exposure-Matched", "Volatility-Matched", "Cash"}
    assert expected <= set(result["metrics"]["benchmarkMetrics"])
    assert result["assumptions"]["fill_price"] == "next_open"
    assert result["assumptions"]["signal_lag_sessions"] == 1
    assert result["executionModel"].endswith("next session open.")


def test_always_long_matches_next_open_buy_and_hold_with_zero_costs(price_history, benchmark_history):
    result = run_research_backtest(
        price_history,
        {"SPY": benchmark_history},
        AlwaysLongStrategy(),
        ExecutionAssumptions(commission_bps=0, slippage_bps=0),
    )

    assert result["metrics"]["totalReturn"] == result["metrics"]["benchmarkMetrics"]["Next-Open Buy & Hold"]["totalReturn"]
    assert [point["strategy"] for point in result["chart"]] == [point["benchmarks"]["Next-Open Buy & Hold"] for point in result["chart"]]


def test_trailing_stop_tracks_from_actual_next_open_entry():
    index = pd.bdate_range("2024-01-02", periods=7)
    opens = [90.0, 104.0, 120.0, 129.0, 117.0, 116.0, 115.0]
    closes = [90.0, 105.0, 115.0, 130.0, 118.0, 117.0, 116.0]
    history = pd.DataFrame(
        {
            "Open": opens,
            "High": [max(open_price, close) + 1 for open_price, close in zip(opens, closes)],
            "Low": [min(open_price, close) - 1 for open_price, close in zip(opens, closes)],
            "Close": closes,
            "Volume": [1_000_000] * len(index),
        },
        index=index,
    )
    strategy = StrategyFactory.create(
        {
            "version": 1,
            "name": "Trailing Stop Fixture",
            "description": "Enter after price crosses 100 and trail the most favorable close.",
            "direction": "long",
            "indicators": {"price": {"type": "price", "source": "close"}},
            "entry": {"all": [{"left": "price", "operator": "crosses_above", "right": 100}]},
            "exit": {"any": [{"left": "price", "operator": "less_than", "right": 1}]},
            "risk": {"trailing_stop_percent": 8},
        }
    )

    result = run_research_backtest(history, {"SPY": history}, strategy)
    closed_trade = next(trade for trade in result["trades"] if trade["status"] == "Closed")

    assert closed_trade["entryDate"] == index[2].strftime("%Y-%m-%d")
    assert closed_trade["entryPrice"] == 120
    assert closed_trade["exitDate"] == index[5].strftime("%Y-%m-%d")
    assert closed_trade["exitPrice"] == 116
    assert result["chart"][4]["signalPosition"] == 0
    assert result["chart"][4]["position"] == 1
    assert result["currentSignal"]["latestTransition"] == {
        "signalDate": index[4].strftime("%Y-%m-%d"),
        "executionDate": index[5].strftime("%Y-%m-%d"),
        "fromState": "LONG",
        "toState": "CASH",
        "executionPrice": 116.0,
        "pendingAtNextOpen": False,
        "reason": "Trailing stop reached at 8% from the favorable close.",
        "ruleValues": {"price": 118.0},
    }


def test_current_signal_uses_the_backtest_final_signal_and_indicator_values(
    price_history,
    benchmark_history,
):
    instance = catalogue.create_instance(
        "sma-crossover",
        {"fast_window": 5, "slow_window": 20},
    )

    result = run_research_backtest(
        price_history,
        {"SPY": benchmark_history},
        catalogue.build(instance),
    )
    current = result["currentSignal"]
    latest_chart = result["chart"][-1]

    expected_target = "LONG" if latest_chart["signalPosition"] > 0 else "CASH"
    expected_executed = "LONG" if latest_chart["position"] > 0 else "CASH"
    assert current["targetState"] == expected_target
    assert current["executedState"] == expected_executed
    assert current["signalPosition"] == latest_chart["signalPosition"]
    assert current["executedPosition"] == latest_chart["position"]
    assert current["observationDate"] == latest_chart["date"]
    assert current["ruleValues"] == latest_chart["indicators"]
    assert "next session open" in current["executionTiming"]
