from __future__ import annotations

from itertools import product
from statistics import median
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from ..strategy.catalogue import StrategyCatalogue
from ..strategy.models import StrategyInstance, ValidationDesign
from .engine import run_research_backtest


def _search_candidates(ranges: dict[str, list[int | float]], cap: int) -> tuple[list[dict[str, int | float]], str]:
    keys = list(ranges)
    combinations = [dict(zip(keys, values)) for values in product(*(ranges[key] for key in keys))]
    if len(keys) <= 2:
        if len(combinations) > cap:
            raise ValueError(f"Exhaustive search contains {len(combinations)} trials; narrow it to at most {cap}.")
        return combinations, "Exhaustive Grid"
    rng = np.random.default_rng(42)
    if len(combinations) <= cap:
        return combinations, "Capped Grid"
    selected = rng.choice(len(combinations), size=cap, replace=False)
    return [combinations[int(index)] for index in selected], "Deterministic Capped Search"


def _walk_forward_score(
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    instance: StrategyInstance,
    catalogue: StrategyCatalogue,
    folds: int,
) -> tuple[float, list[float]]:
    fold_size = max(len(history) // (folds + 1), 30)
    scores: list[float] = []
    strategy = catalogue.build(instance)
    for fold in range(folds):
        validation_start = min(fold_size * (fold + 1), len(history) - 20)
        validation_end = min(validation_start + fold_size, len(history))
        warmup_start = max(0, validation_start - 260)
        segment = history.iloc[warmup_start:validation_end]
        benchmark_segment = benchmark.reindex(segment.index).ffill().bfill()
        if len(segment) < 40:
            continue
        result = run_research_backtest(segment, {"SPY": benchmark_segment}, strategy, instance.execution)
        scores.append(float(result["metrics"]["calmarRatio"]))
    return (median(scores) if scores else float("-inf")), scores


def run_parameter_search(
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    base_instance: StrategyInstance,
    ranges: dict[str, list[int | float]],
    catalogue: StrategyCatalogue,
    validation: ValidationDesign | None = None,
    max_trials: int = 60,
    progress_callback: Callable[[float], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    validation = validation or ValidationDesign()
    if not ranges or len(ranges) > 6:
        raise ValueError("Search between one and six parameters.")
    template = catalogue.get(base_instance.template_id)
    searchable = {parameter.key for parameter in template.parameters if parameter.searchable}
    if not set(ranges) <= searchable:
        raise ValueError("The search includes an unknown or non-searchable parameter.")
    if any(not values for values in ranges.values()):
        raise ValueError("Every searched parameter requires at least one candidate value.")
    final_start = int(len(history) * (1 - validation.final_test_fraction))
    development_history = history.iloc[:final_start]
    development_benchmark = benchmark.reindex(development_history.index).ffill().bfill()
    final_history = history.iloc[max(0, final_start - 260):]
    final_benchmark = benchmark.reindex(final_history.index).ffill().bfill()
    candidates, method = _search_candidates(ranges, min(max_trials, 200))
    attempts: list[dict[str, Any]] = []
    for candidate_number, selected in enumerate(candidates, start=1):
        if cancelled and cancelled():
            raise ValueError("Parameter search was cancelled.")
        values = {**base_instance.parameter_values, **selected}
        candidate = base_instance.model_copy(update={"parameter_values": values})
        try:
            score, fold_scores = _walk_forward_score(development_history, development_benchmark, candidate, catalogue, validation.walk_forward_folds)
            attempts.append({"parameters": selected, "score": round(score, 4), "foldScores": [round(value, 4) for value in fold_scores], "status": "Completed"})
        except ValueError as error:
            attempts.append({"parameters": selected, "score": None, "foldScores": [], "status": "Rejected", "reason": str(error)})
        if progress_callback:
            progress_callback(candidate_number / len(candidates))
    completed = [attempt for attempt in attempts if attempt["score"] is not None]
    if not completed:
        raise ValueError("No valid parameter configuration completed the guarded search.")
    completed.sort(key=lambda attempt: attempt["score"], reverse=True)
    best_values = {**base_instance.parameter_values, **completed[0]["parameters"]}
    best_instance = base_instance.model_copy(update={"parameter_values": best_values})
    final_result = run_research_backtest(final_history, {"SPY": final_benchmark}, catalogue.build(best_instance), best_instance.execution)
    top_score = float(completed[0]["score"])
    stable = [attempt for attempt in completed if float(attempt["score"]) >= top_score * 0.8] if top_score > 0 else []
    return {
        "method": method,
        "objective": "Median Walk-Forward Calmar Ratio",
        "finalTestWasUntouched": True,
        "developmentEnd": development_history.index[-1].strftime("%Y-%m-%d"),
        "finalTestStart": history.index[final_start].strftime("%Y-%m-%d"),
        "bestParameters": completed[0]["parameters"],
        "attempts": attempts,
        "stabilityRegion": [attempt["parameters"] for attempt in stable],
        "performanceDecay": round(top_score - float(final_result["metrics"]["calmarRatio"]), 4),
        "overfittingWarning": "The selected parameters are unstable across nearby settings." if len(stable) < max(2, len(completed) // 10) else None,
        "finalTest": final_result,
    }
