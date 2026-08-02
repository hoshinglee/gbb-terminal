from __future__ import annotations

from typing import Any

import pandas as pd


class IndicatorRegistry:
    """Registry of safe, prebuilt indicators available to YAML strategies."""

    DEFINITIONS = {
        "price": {"description": "Raw OHLCV market field.", "parameters": ["source"]},
        "sma": {"description": "Simple moving average.", "parameters": ["source", "window"]},
        "ema": {"description": "Exponential moving average.", "parameters": ["source", "window"]},
        "rsi": {"description": "Relative Strength Index using Wilder-style smoothing.", "parameters": ["source", "window"]},
        "volume_sma": {"description": "Simple moving average of trading volume.", "parameters": ["window"]},
    }

    @classmethod
    def catalogue(cls) -> list[dict[str, Any]]:
        return [{"type": name, **definition} for name, definition in cls.DEFINITIONS.items()]

    @classmethod
    def calculate(cls, history: pd.DataFrame, specification: dict[str, Any]) -> pd.Series:
        indicator_type = str(specification.get("type", "")).lower()
        if indicator_type not in cls.DEFINITIONS:
            raise ValueError(f"Unsupported indicator '{indicator_type}'.")
        frame = history.rename(columns={column: column.lower() for column in history.columns})
        source = str(specification.get("source", "close")).lower()
        if indicator_type == "volume_sma":
            source = "volume"
        if source not in frame:
            raise ValueError(f"Market field '{source}' is unavailable.")
        values = frame[source].astype(float)
        if indicator_type == "price":
            return values
        window = int(specification.get("window", 0))
        if window <= 0 or window > 500:
            raise ValueError("Indicator window must be between 1 and 500 sessions.")
        if indicator_type in {"sma", "volume_sma"}:
            return values.rolling(window).mean()
        if indicator_type == "ema":
            return values.ewm(span=window, adjust=False).mean()
        delta = values.diff()
        gains = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
        losses = -delta.clip(upper=0).ewm(alpha=1 / window, adjust=False).mean()
        relative_strength = gains / losses.replace(0, float("nan"))
        return (100 - 100 / (1 + relative_strength)).fillna(100)


def technical_indicator_snapshot(history: pd.DataFrame, requests: list[str]) -> pd.DataFrame:
    """Calculate API-friendly indicators such as sma_20 or rsi_14."""
    frame = pd.DataFrame(index=history.index)
    frame["close"] = history["Close"].astype(float)
    frame["volume"] = history["Volume"].fillna(0).astype(float)
    for request in requests:
        if request.lower().startswith("volume_sma_") and request.rsplit("_", 1)[1].isdigit():
            indicator_type, window = "volume_sma", int(request.rsplit("_", 1)[1])
            frame[request.lower()] = IndicatorRegistry.calculate(history, {"type": indicator_type, "window": window})
            continue
        parts = request.lower().split("_")
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError(f"Indicator '{request}' must look like sma_20, ema_20, rsi_14, or volume_sma_20.")
        indicator_type, window = parts[0], int(parts[1])
        frame[request.lower()] = IndicatorRegistry.calculate(history, {"type": indicator_type, "window": window})
    return frame.dropna()
