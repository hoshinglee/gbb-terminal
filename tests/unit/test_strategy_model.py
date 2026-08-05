from __future__ import annotations

import pandas as pd

from gbb_terminal.backtesting.engine import run_research_backtest
from gbb_terminal.backtesting.portfolio import run_ranked_portfolio
from gbb_terminal.strategy.catalogue import catalogue
from gbb_terminal.strategy.indicators.registry import IndicatorRegistry
from gbb_terminal.strategy.models import StrategyInstance


def test_strategy_instance_round_trip_preserves_signals(price_history, benchmark_history):
    original = catalogue.create_instance("darvas-volume-breakout", ticker="AAPL", benchmark="SPY")
    restored = StrategyInstance.model_validate_json(original.model_dump_json())
    first = run_research_backtest(price_history, {"SPY": benchmark_history}, catalogue.build(original))
    second = run_research_backtest(price_history, {"SPY": benchmark_history}, catalogue.build(restored))
    assert [point["position"] for point in first["chart"]] == [point["position"] for point in second["chart"]]
    assert original.semantic_key() == restored.semantic_key()


def test_parameter_change_changes_semantic_identity():
    first = catalogue.create_instance("sma-crossover", {"fast_window": 10, "slow_window": 50}, ticker="AAPL")
    second = catalogue.create_instance("sma-crossover", {"fast_window": 20, "slow_window": 50}, ticker="AAPL")
    assert first.semantic_key() != second.semantic_key()


def test_every_template_executes(price_history, benchmark_history):
    for template in catalogue.list_templates():
        instance = catalogue.create_instance(template.template_id, ticker="AAA", benchmark="SPY", universe=["AAA", "BBB", "CCC"])
        if catalogue.is_portfolio(template.template_id):
            result = run_ranked_portfolio({"AAA": price_history, "BBB": price_history * 1.01, "CCC": price_history * 0.99}, benchmark_history, instance)
        else:
            result = run_research_backtest(price_history, {"SPY": benchmark_history}, catalogue.build(instance))
        assert result["chart"]
        assert result["verdict"]["label"] in {"Robust Candidate", "Promising But Unstable", "Insufficient Evidence", "Does Not Justify Complexity"}


def test_deterministic_levels_do_not_change_with_future_data(price_history):
    cutoff = 410
    specifications = [
        {"type": "donchian_high", "window": 55},
        {"type": "darvas_high", "window": 20, "confirmation_bars": 3},
        {"type": "fibonacci_level", "window": 55, "ratio": 0.618},
    ]
    for specification in specifications:
        full = IndicatorRegistry.calculate(price_history, specification).iloc[:cutoff]
        prefix = IndicatorRegistry.calculate(price_history.iloc[:cutoff], specification)
        pd.testing.assert_series_equal(full, prefix)

