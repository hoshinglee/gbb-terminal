from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def monte_carlo(history: pd.DataFrame, days: int = 252, simulations: int = 400) -> dict[str, Any]:
    returns = history["Close"].pct_change().dropna().to_numpy()
    if len(returns) < 30:
        raise ValueError("Not enough history to run a simulation.")
    rng = np.random.default_rng(42)
    paths = np.cumprod(1 + rng.choice(returns, size=(simulations, days), replace=True), axis=1)
    final_returns, percentiles = (paths[:, -1] - 1) * 100, np.percentile(paths, [10, 50, 90], axis=0)
    chart_indices = np.linspace(0, days - 1, min(days, 100), dtype=int)
    sample_indices = np.linspace(0, simulations - 1, min(simulations, 24), dtype=int)
    return {
        "metrics": {
            "medianReturn": round(float(np.median(final_returns)), 2),
            "upsideReturn": round(float(np.percentile(final_returns, 90)), 2),
            "downsideReturn": round(float(np.percentile(final_returns, 10)), 2),
            "profitProbability": round(float((final_returns > 0).mean() * 100), 1),
        },
        "paths": [{"day": int(index + 1), "p10": round(float(percentiles[0, index]), 4), "p50": round(float(percentiles[1, index]), 4), "p90": round(float(percentiles[2, index]), 4)} for index in chart_indices],
        "samplePaths": [[round(float(paths[path_index, day_index]), 4) for day_index in chart_indices] for path_index in sample_indices],
    }

