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

