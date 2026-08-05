from __future__ import annotations

from collections.abc import Callable
from itertools import product
from math import e, sqrt
from statistics import NormalDist, median
from typing import Any

import numpy as np
import pandas as pd

from ..strategy.catalogue import StrategyCatalogue
from ..strategy.models import ParameterType, StrategyInstance, ValidationDesign
from .engine import run_research_backtest
from .metrics import EvidenceContext


def _walk_forward_windows(history: pd.DataFrame, validation: ValidationDesign) -> tuple[int, int, list[dict[str, Any]]]:
    final_start = int(len(history) * (1 - validation.final_test_fraction))
    training_end = int(len(history) * validation.training_fraction)
    if final_start >= len(history) or training_end >= final_start:
        raise ValueError("Validation design does not leave distinct training, walk-forward, and final-test windows.")
    validation_rows = np.arange(training_end, final_start)
    folds = [rows for rows in np.array_split(validation_rows, validation.walk_forward_folds) if len(rows)]
    if len(folds) != validation.walk_forward_folds or any(len(rows) < 10 for rows in folds):
        raise ValueError("The selected history is too short for the requested walk-forward design.")
    windows = [
        {
            "fold": number,
            "evaluationStartRow": int(rows[0]),
            "evaluationEndRow": int(rows[-1]),
            "evaluationStart": history.index[int(rows[0])].strftime("%Y-%m-%d"),
            "evaluationEnd": history.index[int(rows[-1])].strftime("%Y-%m-%d"),
        }
        for number, rows in enumerate(folds, start=1)
    ]
    return training_end, final_start, windows


def _walk_forward_score(
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    instance: StrategyInstance,
    catalogue: StrategyCatalogue,
    windows: list[dict[str, Any]],
) -> tuple[float, list[float], list[float]]:
    scores: list[float] = []
    sharpes: list[float] = []
    strategy = catalogue.build(instance)
    for window in windows:
        evaluation_start_row = int(window["evaluationStartRow"])
        evaluation_end_row = int(window["evaluationEndRow"])
        warmup_start = max(0, evaluation_start_row - 520)
        segment = history.iloc[warmup_start : evaluation_end_row + 1]
        benchmark_segment = benchmark.reindex(segment.index).ffill()
        result = run_research_backtest(
            segment,
            {instance.benchmark: benchmark_segment},
            strategy,
            instance.execution,
            evaluation_start=history.index[evaluation_start_row],
        )
        scores.append(float(result["metrics"]["calmarRatio"]))
        sharpes.append(float(result["metrics"]["sharpeRatio"]))
    return median(scores), scores, sharpes


def _validated_ranges(
    ranges: dict[str, list[int | float]],
    base_instance: StrategyInstance,
    catalogue: StrategyCatalogue,
) -> dict[str, list[int | float]]:
    if not ranges or len(ranges) > 6:
        raise ValueError("Search between one and six parameters.")
    template = catalogue.get(base_instance.template_id)
    specifications = {parameter.key: parameter for parameter in template.parameters if parameter.searchable}
    if not set(ranges) <= set(specifications):
        raise ValueError("The search includes an unknown or non-searchable parameter.")
    validated: dict[str, list[int | float]] = {}
    for key, values in ranges.items():
        if not values:
            raise ValueError("Every searched parameter requires at least one candidate value.")
        specification = specifications[key]
        candidates = list(dict.fromkeys(values))
        for value in candidates:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                raise ValueError(f"Search values for {specification.label} must be finite numbers.")
            if specification.parameter_type == ParameterType.INTEGER and int(value) != value:
                raise ValueError(f"Search values for {specification.label} must be integers.")
            if specification.minimum is not None and value < specification.minimum:
                raise ValueError(f"Search values for {specification.label} cannot be below {specification.minimum:g}.")
            if specification.maximum is not None and value > specification.maximum:
                raise ValueError(f"Search values for {specification.label} cannot exceed {specification.maximum:g}.")
        validated[key] = candidates
    return validated


def _parameter_heatmap(attempts: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    completed = [attempt for attempt in attempts if attempt.get("score") is not None]
    if not completed:
        return {"xParameter": keys[0], "yParameter": keys[1] if len(keys) > 1 else None, "cells": []}
    x_parameter = keys[0]
    y_parameter = keys[1] if len(keys) > 1 else None
    grouped: dict[tuple[int | float, int | float | None], list[float]] = {}
    for attempt in completed:
        coordinate = (attempt["parameters"][x_parameter], attempt["parameters"].get(y_parameter) if y_parameter else None)
        grouped.setdefault(coordinate, []).append(float(attempt["score"]))
    cells = [
        {"x": coordinate[0], "y": coordinate[1], "medianScore": round(median(scores), 4), "trials": len(scores)}
        for coordinate, scores in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] if item[0][1] is not None else 0))
    ]
    return {"xParameter": x_parameter, "yParameter": y_parameter, "cells": cells}


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
    comparison_benchmarks: dict[str, pd.DataFrame] | None = None,
    peer_histories: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    validation = validation or ValidationDesign()
    ranges = _validated_ranges(ranges, base_instance, catalogue)
    training_end, final_start, windows = _walk_forward_windows(history, validation)
    development_history = history.iloc[:final_start]
    development_benchmark = benchmark.reindex(development_history.index).ffill()
    attempts: list[dict[str, Any]] = []

    def evaluate(selected: dict[str, int | float], trial_number: int) -> float:
        if cancelled and cancelled():
            raise ValueError("Parameter search was cancelled.")
        values = {**base_instance.parameter_values, **selected}
        candidate = base_instance.model_copy(update={"parameter_values": values})
        try:
            score, fold_scores, fold_sharpes = _walk_forward_score(
                development_history,
                development_benchmark,
                candidate,
                catalogue,
                windows,
            )
            attempts.append(
                {
                    "trial": trial_number,
                    "parameters": selected,
                    "score": round(score, 4),
                    "foldScores": [round(value, 4) for value in fold_scores],
                    "foldSharpes": [round(value, 4) for value in fold_sharpes],
                    "status": "Completed",
                }
            )
            return score
        except ValueError as error:
            attempts.append(
                {
                    "trial": trial_number,
                    "parameters": selected,
                    "score": None,
                    "foldScores": [],
                    "foldSharpes": [],
                    "status": "Rejected",
                    "reason": str(error),
                }
            )
            return -1e12

    total_combinations = int(np.prod([len(values) for values in ranges.values()]))
    if len(ranges) <= 2:
        if total_combinations > max_trials:
            raise ValueError(f"Exhaustive search contains {total_combinations} trials; narrow it to at most {max_trials}.")
        method = "Exhaustive Grid"
        combinations = [dict(zip(ranges, values)) for values in product(*(ranges[key] for key in ranges))]
        for trial_number, selected in enumerate(combinations, start=1):
            evaluate(selected, trial_number)
            if progress_callback:
                progress_callback(trial_number / len(combinations))
    else:
        try:
            import optuna
        except ImportError as error:
            raise ValueError("Optuna is required for searches over three to six parameters; reinstall GBB Terminal dependencies.") from error
        method = "Optuna TPE"
        trial_count = min(max_trials, total_combinations)
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        defaults = {key: base_instance.parameter_values[key] for key in ranges if base_instance.parameter_values.get(key) in ranges[key]}
        if len(defaults) == len(ranges):
            study.enqueue_trial(defaults, skip_if_exists=True)

        def objective(trial) -> float:
            selected = {key: trial.suggest_categorical(key, values) for key, values in ranges.items()}
            score = evaluate(selected, trial.number + 1)
            if progress_callback:
                progress_callback((trial.number + 1) / trial_count)
            return score

        study.optimize(objective, n_trials=trial_count, catch=())

    completed = [attempt for attempt in attempts if attempt["score"] is not None]
    if not completed:
        raise ValueError("No valid parameter configuration completed the guarded search.")
    completed.sort(key=lambda attempt: float(attempt["score"]), reverse=True)
    best_parameters = completed[0]["parameters"]
    best_values = {**base_instance.parameter_values, **best_parameters}
    best_instance = base_instance.model_copy(update={"parameter_values": best_values})
    top_score = float(completed[0]["score"])
    score_values = [float(attempt["score"]) for attempt in completed]
    stability_tolerance = max(abs(top_score) * 0.2, float(np.std(score_values, ddof=0)) * 0.5, 0.1)
    stable = [attempt for attempt in completed if float(attempt["score"]) >= top_score - stability_tolerance]
    unique_stable = {tuple(sorted(attempt["parameters"].items())) for attempt in stable}
    unique_completed = {tuple(sorted(attempt["parameters"].items())) for attempt in completed}
    stable_parameters = len(unique_stable) >= max(2, int(np.ceil(len(unique_completed) * 0.1)))
    deflated_probability = _deflated_sharpe_probability(completed, final_start - training_end)

    final_history = history.iloc[max(0, final_start - 520) :]
    final_benchmark = benchmark.reindex(final_history.index).ffill()
    final_comparisons = {base_instance.benchmark: final_benchmark}
    for label, comparison in (comparison_benchmarks or {}).items():
        if label not in final_comparisons:
            final_comparisons[label] = comparison.reindex(final_history.index).ffill()
    final_peers = {
        symbol: peer.reindex(final_history.index).ffill()
        for symbol, peer in (peer_histories or {}).items()
    }
    context = EvidenceContext(
        out_of_sample=True,
        stable_parameters=stable_parameters,
        deflated_sharpe_probability=deflated_probability,
        walk_forward_folds=validation.walk_forward_folds,
    )
    final_result = run_research_backtest(
        final_history,
        final_comparisons,
        catalogue.build(best_instance),
        best_instance.execution,
        peer_histories=final_peers,
        evaluation_start=history.index[final_start],
        evidence_context=context,
    )
    return {
        "method": method,
        "objective": "Median Walk-Forward Calmar Ratio",
        "seed": 42 if method == "Optuna TPE" else None,
        "finalTestWasUntouched": True,
        "trainingEnd": history.index[training_end - 1].strftime("%Y-%m-%d"),
        "developmentEnd": development_history.index[-1].strftime("%Y-%m-%d"),
        "finalTestStart": history.index[final_start].strftime("%Y-%m-%d"),
        "validationWindows": [{key: value for key, value in window.items() if not key.endswith("Row")} for window in windows],
        "bestParameters": best_parameters,
        "bestStrategy": best_instance.model_dump(mode="json"),
        "attempts": attempts,
        "heatmap": _parameter_heatmap(attempts, list(ranges)),
        "stabilityRegion": [attempt["parameters"] for attempt in stable],
        "stableParameters": stable_parameters,
        "performanceDecay": round(top_score - float(final_result["metrics"]["calmarRatio"]), 4),
        "deflatedSharpeProbability": round(deflated_probability * 100, 1),
        "overfittingWarning": (
            "Selection-adjusted Sharpe evidence or nearby-parameter stability is weak."
            if deflated_probability < 0.8 or not stable_parameters
            else None
        ),
        "finalTest": final_result,
    }


def _deflated_sharpe_probability(attempts: list[dict[str, Any]], observations: int) -> float:
    candidate_sharpes = [median(attempt["foldSharpes"]) for attempt in attempts if attempt.get("foldSharpes")]
    if not candidate_sharpes:
        return 0.0
    observed = max(candidate_sharpes)
    if len(candidate_sharpes) == 1:
        expected_maximum = 0.0
    else:
        standard_deviation = float(np.std(candidate_sharpes, ddof=1))
        normal = NormalDist()
        trials = len(candidate_sharpes)
        expected_maximum = standard_deviation * (
            0.5772156649 * normal.inv_cdf(1 - 1 / (trials * e))
            + (1 - 0.5772156649) * normal.inv_cdf(1 - 1 / trials)
        )
    standard_error = sqrt(max((1 + 0.5 * observed**2) / max(observations - 1, 1), 1e-12))
    return NormalDist().cdf((observed - expected_maximum) / standard_error)
