from __future__ import annotations

import hashlib

import pandas as pd

from ..strategy.models import DataSnapshot


SNAPSHOT_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def create_data_snapshot(symbol: str, history: pd.DataFrame) -> DataSnapshot:
    if history.empty:
        raise ValueError(f"Cannot fingerprint empty history for {symbol}.")
    missing = [column for column in SNAPSHOT_COLUMNS if column not in history]
    if missing:
        raise ValueError(f"History for {symbol} is missing snapshot fields: {', '.join(missing)}.")
    normalized = history.loc[:, SNAPSHOT_COLUMNS].copy().sort_index()
    normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
    if normalized.index.has_duplicates:
        raise ValueError(f"History for {symbol} contains duplicate sessions.")
    payload = normalized.to_csv(
        index=True,
        index_label="Date",
        date_format="%Y-%m-%dT%H:%M:%S",
        float_format="%.17g",
        lineterminator="\n",
    ).encode()
    return DataSnapshot(
        symbol=symbol.upper(),
        start_date=normalized.index[0].date(),
        end_date=normalized.index[-1].date(),
        rows=len(normalized),
        columns=SNAPSHOT_COLUMNS,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def create_snapshot_manifest(histories: dict[str, pd.DataFrame]) -> dict[str, DataSnapshot]:
    return {symbol.upper(): create_data_snapshot(symbol, history) for symbol, history in sorted(histories.items())}
