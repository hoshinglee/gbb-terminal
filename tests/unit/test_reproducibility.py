from __future__ import annotations

from gbb_terminal.backtesting.snapshots import create_data_snapshot, create_snapshot_manifest
from gbb_terminal.strategy.catalogue import catalogue
from gbb_terminal.strategy.models import ENGINE_VERSION, ResearchRun, StrategyInstance
import pytest


def test_data_snapshot_is_deterministic_and_changes_with_price_data(price_history):
    first = create_data_snapshot("aapl", price_history)
    second = create_data_snapshot("AAPL", price_history.copy())
    changed = price_history.copy()
    changed.iloc[-1, changed.columns.get_loc("Close")] += 0.01

    assert first == second
    assert first.symbol == "AAPL"
    assert first.rows == len(price_history)
    assert first.sha256 != create_data_snapshot("AAPL", changed).sha256


def test_research_run_round_trip_locks_reproducibility_identity(price_history, benchmark_history):
    strategy = catalogue.create_instance("donchian-breakout", ticker="aapl", benchmark="spy")
    snapshots = create_snapshot_manifest({"AAPL": price_history, "SPY": benchmark_history})
    original = ResearchRun(strategy=strategy, data_snapshot=snapshots, results={"metrics": {"totalReturn": 1.2}})
    restored = ResearchRun.model_validate_json(original.model_dump_json())

    assert restored.strategy == StrategyInstance.model_validate_json(strategy.model_dump_json())
    assert restored.engine_version == ENGINE_VERSION
    assert restored.strategy_key == strategy.semantic_key()
    assert restored.reproducibility_key == original.reproducibility_key


def test_research_run_rejects_spoofed_reproducibility_keys(price_history):
    strategy = catalogue.create_instance("sma-crossover", ticker="AAPL")
    snapshots = create_snapshot_manifest({"AAPL": price_history})

    with pytest.raises(ValueError, match="strategy key"):
        ResearchRun(strategy=strategy, strategy_key="wrong", data_snapshot=snapshots)
    with pytest.raises(ValueError, match="reproducibility key"):
        ResearchRun(strategy=strategy, data_snapshot=snapshots, reproducibility_key="wrong")


def test_every_single_stock_template_preserves_signals_after_serialization(price_history, benchmark_history):
    for template in catalogue.list_templates():
        if catalogue.is_portfolio(template.template_id):
            continue
        original = catalogue.create_instance(template.template_id, ticker="AAA", benchmark="SPY")
        restored = StrategyInstance.model_validate_json(original.model_dump_json())
        strategy_history = price_history.assign(Benchmark_Close=benchmark_history["Close"])
        original_positions = catalogue.build(original).positions(strategy_history)["position"]
        restored_positions = catalogue.build(restored).positions(strategy_history)["position"]
        assert original_positions.equals(restored_positions), template.template_id


def test_core_family_signals_do_not_change_when_future_prices_change(price_history):
    cutoff = 420
    changed = price_history.copy()
    changed.iloc[cutoff:, changed.columns.get_loc("Close")] *= 3
    changed.iloc[cutoff:, changed.columns.get_loc("High")] *= 3
    changed.iloc[cutoff:, changed.columns.get_loc("Low")] *= 3
    for template_id in ("sma-crossover", "rsi-mean-reversion", "donchian-breakout"):
        strategy = catalogue.build(catalogue.create_instance(template_id, ticker="AAA"))
        original = strategy.positions(price_history)["position"].iloc[:cutoff]
        mutated = strategy.positions(changed)["position"].iloc[:cutoff]
        assert original.equals(mutated), template_id
