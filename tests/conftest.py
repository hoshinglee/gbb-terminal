from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def price_history() -> pd.DataFrame:
    index = pd.bdate_range("2022-01-03", periods=620)
    random = np.random.default_rng(17)
    close = 100 * np.cumprod(1 + random.normal(0.00045, 0.012, len(index)))
    return pd.DataFrame(
        {
            "Open": close * (1 + random.normal(0, 0.002, len(index))),
            "High": close * 1.012,
            "Low": close * 0.988,
            "Close": close,
            "Volume": random.integers(750_000, 5_000_000, len(index)),
        },
        index=index,
    )


@pytest.fixture
def benchmark_history(price_history: pd.DataFrame) -> pd.DataFrame:
    benchmark = price_history.copy()
    benchmark["Close"] = 100 * (1 + price_history["Close"].pct_change().fillna(0) * 0.7).cumprod()
    benchmark["Open"] = benchmark["Close"] * 0.999
    benchmark["High"] = benchmark["Close"] * 1.008
    benchmark["Low"] = benchmark["Close"] * 0.992
    return benchmark

