from gbb_terminal.backtesting.parameter_search import run_parameter_search
from gbb_terminal.strategy.catalogue import catalogue
from gbb_terminal.strategy.models import ValidationDesign


def test_parameter_search_preserves_final_window(price_history, benchmark_history):
    instance = catalogue.create_instance("sma-crossover", {"fast_window": 10, "slow_window": 40}, ticker="AAPL")
    result = run_parameter_search(
        price_history,
        benchmark_history,
        instance,
        {"fast_window": [5, 10], "slow_window": [30, 40]},
        catalogue,
        ValidationDesign(final_test_fraction=0.2),
        max_trials=10,
    )
    assert result["finalTestWasUntouched"] is True
    assert len(result["attempts"]) == 4
    assert result["developmentEnd"] < result["finalTestStart"]
    assert result["heatmap"]["cells"]
    assert result["finalTest"]["evaluationPeriod"]["start"] == result["finalTestStart"]


def test_final_window_cannot_change_selected_parameters(price_history, benchmark_history):
    instance = catalogue.create_instance("sma-crossover", {"fast_window": 10, "slow_window": 40}, ticker="AAPL")
    validation = ValidationDesign(final_test_fraction=0.2)
    original = run_parameter_search(
        price_history,
        benchmark_history,
        instance,
        {"fast_window": [5, 10], "slow_window": [30, 40]},
        catalogue,
        validation,
        max_trials=10,
    )
    changed = price_history.copy()
    final_start = int(len(changed) * (1 - validation.final_test_fraction))
    changed.iloc[final_start:, changed.columns.get_loc("Close")] *= 4
    changed.iloc[final_start:, changed.columns.get_loc("Open")] *= 4
    changed.iloc[final_start:, changed.columns.get_loc("High")] *= 4
    changed.iloc[final_start:, changed.columns.get_loc("Low")] *= 4
    mutated = run_parameter_search(
        changed,
        benchmark_history,
        instance,
        {"fast_window": [5, 10], "slow_window": [30, 40]},
        catalogue,
        validation,
        max_trials=10,
    )

    assert mutated["bestParameters"] == original["bestParameters"]
    assert mutated["attempts"] == original["attempts"]
    assert mutated["finalTest"]["metrics"] != original["finalTest"]["metrics"]


def test_three_parameter_optuna_search_is_seeded_and_repeatable(price_history, benchmark_history):
    instance = catalogue.create_instance("macd-trend", ticker="AAPL")
    arguments = (
        price_history,
        benchmark_history,
        instance,
        {"fast_window": [8, 12], "slow_window": [24, 30], "signal_window": [7, 9]},
        catalogue,
    )

    first = run_parameter_search(*arguments, max_trials=8)
    second = run_parameter_search(*arguments, max_trials=8)

    assert first["method"] == "Optuna TPE"
    assert first["seed"] == 42
    assert first["bestParameters"] == second["bestParameters"]
    assert first["attempts"] == second["attempts"]
