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
        "rolling_std": {"description": "Rolling standard deviation.", "parameters": ["source", "window"]},
        "bollinger_upper": {"description": "Upper Bollinger Band.", "parameters": ["source", "window", "deviations"]},
        "bollinger_lower": {"description": "Lower Bollinger Band.", "parameters": ["source", "window", "deviations"]},
        "macd": {"description": "Moving-average convergence divergence line.", "parameters": ["fast_window", "slow_window"]},
        "macd_signal": {"description": "MACD signal line.", "parameters": ["fast_window", "slow_window", "signal_window"]},
        "atr": {"description": "Average True Range.", "parameters": ["window"]},
        "donchian_high": {"description": "Prior rolling channel high.", "parameters": ["window"]},
        "donchian_low": {"description": "Prior rolling channel low.", "parameters": ["window"]},
        "darvas_high": {"description": "Deterministic confirmed Darvas-box ceiling.", "parameters": ["window", "confirmation_bars"]},
        "darvas_low": {"description": "Deterministic confirmed Darvas-box floor.", "parameters": ["window", "confirmation_bars"]},
        "obv": {"description": "On-balance volume.", "parameters": []},
        "zscore": {"description": "Rolling price z-score.", "parameters": ["source", "window"]},
        "volatility": {"description": "Annualized rolling realized volatility.", "parameters": ["source", "window"]},
        "gap": {"description": "Opening gap from prior close, in percent.", "parameters": []},
        "fibonacci_level": {"description": "Deterministic rolling swing Fibonacci level.", "parameters": ["window", "ratio"]},
        "relative_strength": {"description": "Rolling return relative to an aligned benchmark.", "parameters": ["window"]},
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
        if indicator_type in {"volume_sma", "obv"}:
            source = "volume"
        if indicator_type in {"atr", "donchian_high", "donchian_low", "darvas_high", "darvas_low", "gap", "fibonacci_level", "relative_strength"}:
            source = "close"
        if source not in frame:
            raise ValueError(f"Market field '{source}' is unavailable.")
        values = frame[source].astype(float)
        if indicator_type == "price":
            return values
        if indicator_type == "obv":
            direction = frame["close"].diff().apply(lambda change: 1 if change > 0 else -1 if change < 0 else 0)
            return (frame["volume"].astype(float) * direction).cumsum()
        if indicator_type == "gap":
            return (frame["open"].astype(float) / frame["close"].astype(float).shift(1) - 1) * 100
        window = int(specification.get("slow_window", 0)) if indicator_type in {"macd", "macd_signal"} else int(specification.get("window", 0))
        if window <= 0 or window > 500:
            raise ValueError("Indicator window must be between 1 and 500 sessions.")
        if indicator_type in {"sma", "volume_sma"}:
            return values.rolling(window).mean()
        if indicator_type == "ema":
            return values.ewm(span=window, adjust=False).mean()
        if indicator_type == "rolling_std":
            return values.rolling(window).std(ddof=0)
        if indicator_type in {"bollinger_upper", "bollinger_lower"}:
            deviations = float(specification.get("deviations", 2.0))
            if deviations <= 0 or deviations > 10:
                raise ValueError("Bollinger deviations must be greater than 0 and at most 10.")
            middle, deviation = values.rolling(window).mean(), values.rolling(window).std(ddof=0)
            return middle + deviation * deviations * (1 if indicator_type == "bollinger_upper" else -1)
        if indicator_type in {"macd", "macd_signal"}:
            fast_window = int(specification.get("fast_window", 12))
            slow_window = int(specification.get("slow_window", 26))
            signal_window = int(specification.get("signal_window", 9))
            if not 1 < fast_window < slow_window <= 500 or not 1 < signal_window <= 500:
                raise ValueError("MACD windows must be valid and the fast window must be shorter.")
            macd = values.ewm(span=fast_window, adjust=False).mean() - values.ewm(span=slow_window, adjust=False).mean()
            return macd if indicator_type == "macd" else macd.ewm(span=signal_window, adjust=False).mean()
        if indicator_type == "atr":
            high, low, previous_close = frame["high"].astype(float), frame["low"].astype(float), frame["close"].astype(float).shift(1)
            true_range = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
            return true_range.ewm(alpha=1 / window, adjust=False).mean()
        if indicator_type == "donchian_high":
            return frame["high"].astype(float).rolling(window).max().shift(1)
        if indicator_type == "donchian_low":
            return frame["low"].astype(float).rolling(window).min().shift(1)
        if indicator_type in {"darvas_high", "darvas_low"}:
            confirmation_bars = int(specification.get("confirmation_bars", 3))
            if confirmation_bars < 1 or confirmation_bars > 20:
                raise ValueError("Darvas confirmation bars must be between 1 and 20.")
            field = "high" if indicator_type == "darvas_high" else "low"
            reducer = "max" if field == "high" else "min"
            rolling = getattr(frame[field].astype(float).rolling(window), reducer)().shift(confirmation_bars)
            return rolling.ffill()
        if indicator_type == "zscore":
            mean, deviation = values.rolling(window).mean(), values.rolling(window).std(ddof=0)
            return (values - mean) / deviation.replace(0, float("nan"))
        if indicator_type == "volatility":
            return values.pct_change().rolling(window).std(ddof=0) * (252**0.5) * 100
        if indicator_type == "fibonacci_level":
            ratio = float(specification.get("ratio", 0.618))
            if ratio <= 0 or ratio >= 1:
                raise ValueError("A Fibonacci ratio must be between 0 and 1.")
            swing_high = frame["high"].astype(float).rolling(window).max().shift(1)
            swing_low = frame["low"].astype(float).rolling(window).min().shift(1)
            return swing_high - (swing_high - swing_low) * ratio
        if indicator_type == "relative_strength":
            if "benchmark_close" not in frame:
                raise ValueError("Relative strength requires an aligned benchmark_close field.")
            stock_return = values / values.shift(window) - 1
            benchmark = frame["benchmark_close"].astype(float)
            return (stock_return - (benchmark / benchmark.shift(window) - 1)) * 100
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
