from __future__ import annotations

from typing import Any

import pandas as pd

from ..strategy.indicators.registry import IndicatorRegistry


INTERVAL_FREQUENCIES = {
    "day": None,
    "week": "W-FRI",
    "month": "M",
    "year": "Y",
}


def _aggregate_ohlcv(history: pd.DataFrame, frequency: str | None) -> tuple[pd.DataFrame, list[pd.Timestamp], list[pd.Timestamp]]:
    if frequency is None:
        frame = history.copy()
        dates = [pd.Timestamp(index) for index in frame.index]
        return frame, dates, dates

    rows: list[dict[str, float]] = []
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for _, group in history.groupby(history.index.to_period(frequency), sort=True):
        row = {
            "Open": float(group["Open"].iloc[0]),
            "High": float(group["High"].max()),
            "Low": float(group["Low"].min()),
            "Close": float(group["Close"].iloc[-1]),
            "Volume": float(group["Volume"].sum()),
        }
        for column in ("Position", "SignalPosition", "StrategyEquity"):
            if column in group:
                row[column] = float(group[column].iloc[-1])
        rows.append(row)
        starts.append(pd.Timestamp(group.index[0]))
        ends.append(pd.Timestamp(group.index[-1]))
    return pd.DataFrame(rows, index=ends), starts, ends


def _indicator_frame(history: pd.DataFrame) -> pd.DataFrame:
    indicators = pd.DataFrame(index=history.index)
    indicators["sma20"] = IndicatorRegistry.calculate(history, {"type": "sma", "source": "close", "window": 20})
    indicators["ema20"] = IndicatorRegistry.calculate(history, {"type": "ema", "source": "close", "window": 20})
    indicators["bollingerMiddle20"] = indicators["sma20"]
    indicators["bollingerUpper20"] = IndicatorRegistry.calculate(
        history,
        {"type": "bollinger_upper", "source": "close", "window": 20, "deviations": 2},
    )
    indicators["bollingerLower20"] = IndicatorRegistry.calculate(
        history,
        {"type": "bollinger_lower", "source": "close", "window": 20, "deviations": 2},
    )
    indicators["volumeSma20"] = IndicatorRegistry.calculate(history, {"type": "volume_sma", "window": 20})
    indicators["rsi14"] = IndicatorRegistry.calculate(history, {"type": "rsi", "source": "close", "window": 14})
    indicators["macd"] = IndicatorRegistry.calculate(
        history,
        {"type": "macd", "source": "close", "fast_window": 12, "slow_window": 26},
    )
    indicators["macdSignal"] = IndicatorRegistry.calculate(
        history,
        {"type": "macd_signal", "source": "close", "fast_window": 12, "slow_window": 26, "signal_window": 9},
    )
    indicators["macdHistogram"] = indicators["macd"] - indicators["macdSignal"]
    return indicators


def _number(value: Any, decimals: int = 4) -> float | None:
    return round(float(value), decimals) if pd.notna(value) else None


def _chart_points(history: pd.DataFrame, starts: list[pd.Timestamp], ends: list[pd.Timestamp]) -> list[dict[str, Any]]:
    indicators = _indicator_frame(history)
    points: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(history.iterrows()):
        indicator_values = {
            name: _number(indicators.loc[index, name])
            for name in indicators.columns
        }
        points.append(
            {
                "date": pd.Timestamp(index).strftime("%Y-%m-%d"),
                "periodStart": starts[position].strftime("%Y-%m-%d"),
                "periodEnd": ends[position].strftime("%Y-%m-%d"),
                "open": _number(row["Open"]),
                "high": _number(row["High"]),
                "low": _number(row["Low"]),
                "close": _number(row["Close"]),
                "volume": round(float(row["Volume"])),
                "indicators": indicator_values,
            }
        )
        for source, target in (
            ("Position", "position"),
            ("SignalPosition", "signalPosition"),
            ("StrategyEquity", "strategyEquity"),
        ):
            if source in row:
                points[-1][target] = _number(row[source])
    return points


def _visible_interval_points(
    history: pd.DataFrame,
    frequency: str | None,
    visible_start: pd.Timestamp,
    visible_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    visible_source = history.loc[(history.index >= visible_start) & (history.index <= visible_end)]
    if visible_source.empty:
        return []
    warmup_source = history.loc[history.index < visible_start]
    if frequency is not None and not warmup_source.empty:
        first_visible_period = visible_source.index[0].to_period(frequency)
        warmup_source = warmup_source.loc[warmup_source.index.to_period(frequency) != first_visible_period]
    warmup, warmup_starts, warmup_ends = _aggregate_ohlcv(warmup_source, frequency) if not warmup_source.empty else (pd.DataFrame(), [], [])
    visible, visible_starts, visible_ends = _aggregate_ohlcv(visible_source, frequency)
    combined = pd.concat([warmup, visible]) if not warmup.empty else visible
    points = _chart_points(combined, [*warmup_starts, *visible_starts], [*warmup_ends, *visible_ends])
    return points[-len(visible):]


def build_market_chart(
    history: pd.DataFrame,
    *,
    visible_start: pd.Timestamp | str | None = None,
    visible_end: pd.Timestamp | str | None = None,
    research_state: pd.DataFrame | None = None,
) -> dict[str, Any]:
    columns = ["Open", "High", "Low", "Close", "Volume"]
    canonical = history[columns].copy().sort_index()
    canonical.index = pd.to_datetime(canonical.index).tz_localize(None)
    if research_state is not None:
        normalized_state = research_state.copy()
        normalized_state.index = pd.to_datetime(normalized_state.index).tz_localize(None)
        for column in ("Position", "SignalPosition", "StrategyEquity"):
            if column in normalized_state:
                canonical[column] = normalized_state[column].reindex(canonical.index)
    else:
        for column in ("Position", "SignalPosition", "StrategyEquity"):
            if column in history:
                values = history[column].copy()
                values.index = pd.to_datetime(values.index).tz_localize(None)
                canonical[column] = values.reindex(canonical.index)
    start = pd.Timestamp(visible_start).tz_localize(None) if visible_start is not None else canonical.index[0]
    end = pd.Timestamp(visible_end).tz_localize(None) if visible_end is not None else canonical.index[-1]
    if start > end:
        raise ValueError("Market chart start must not be after its end.")
    intervals: dict[str, list[dict[str, Any]]] = {}
    for interval, frequency in INTERVAL_FREQUENCIES.items():
        intervals[interval] = _visible_interval_points(canonical, frequency, start, end)
    return {
        "defaultInterval": "day",
        "intervals": intervals,
        "indicatorSettings": {
            "sma": {"window": 20},
            "ema": {"window": 20},
            "bollinger": {"window": 20, "deviations": 2},
            "volumeAverage": {"window": 20},
            "rsi": {"window": 14},
            "macd": {"fastWindow": 12, "slowWindow": 26, "signalWindow": 9},
        },
    }
