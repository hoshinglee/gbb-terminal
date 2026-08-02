from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd


class LocalMarketStore:
    """A local DuckDB cache for requested Yahoo Finance data."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(database_path))
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                symbol VARCHAR NOT NULL,
                price_date DATE NOT NULL,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                fetched_at TIMESTAMP NOT NULL,
                PRIMARY KEY (symbol, price_date)
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS option_chains (
                symbol VARCHAR PRIMARY KEY,
                fetched_at TIMESTAMP NOT NULL,
                payload JSON NOT NULL
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS strategy_catalogue (
                strategy_id VARCHAR PRIMARY KEY,
                fingerprint VARCHAR UNIQUE NOT NULL,
                instruction VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                description VARCHAR NOT NULL,
                strategy_type VARCHAR NOT NULL,
                direction VARCHAR NOT NULL,
                parameters JSON NOT NULL,
                provider VARCHAR NOT NULL,
                strategy_yaml VARCHAR,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS strategy_yaml VARCHAR")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id VARCHAR PRIMARY KEY,
                strategy_id VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                run_window VARCHAR NOT NULL,
                metrics JSON NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS backtest_trades (
                run_id VARCHAR NOT NULL,
                trade_number INTEGER NOT NULL,
                entry_date DATE NOT NULL,
                entry_price DOUBLE NOT NULL,
                exit_date DATE NOT NULL,
                exit_price DOUBLE NOT NULL,
                side VARCHAR NOT NULL,
                pnl DOUBLE NOT NULL,
                pnl_percent DOUBLE NOT NULL,
                PRIMARY KEY (run_id, trade_number)
            )
        """)

    def load_history(self, symbol: str, period: str, max_age_minutes: int = 15) -> pd.DataFrame | None:
        newest = self.connection.execute(
            "SELECT max(fetched_at) FROM price_history WHERE symbol = ?", [symbol]
        ).fetchone()[0]
        if newest is None or datetime.now(timezone.utc).replace(tzinfo=None) - newest > timedelta(minutes=max_age_minutes):
            return None
        days = {"1mo": 40, "3mo": 110, "6mo": 200, "1y": 370, "2y": 740}.get(period, 740)
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        frame = self.connection.execute(
            """SELECT price_date AS Date, open AS Open, high AS High, low AS Low,
                      close AS Close, volume AS Volume
               FROM price_history WHERE symbol = ? AND price_date >= ? ORDER BY price_date""",
            [symbol, start_date],
        ).df()
        if frame.empty or len(frame) < 20 or frame["Date"].min().date() > start_date:
            return None
        frame["Date"] = pd.to_datetime(frame["Date"])
        return frame.set_index("Date")

    def save_history(self, symbol: str, frame: pd.DataFrame) -> None:
        rows = frame.copy().reset_index().rename(columns={"index": "Date"})
        rows["symbol"] = symbol
        rows["price_date"] = pd.to_datetime(rows["Date"]).dt.date
        rows["fetched_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = rows.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        self.connection.register("incoming_prices", rows[["symbol", "price_date", "open", "high", "low", "close", "volume", "fetched_at"]])
        self.connection.execute("DELETE FROM price_history WHERE symbol = ?", [symbol])
        self.connection.execute("INSERT INTO price_history SELECT * FROM incoming_prices")
        self.connection.unregister("incoming_prices")

    def load_options(self, symbol: str, max_age_minutes: int = 15) -> dict | None:
        row = self.connection.execute(
            "SELECT fetched_at, payload FROM option_chains WHERE symbol = ?", [symbol]
        ).fetchone()
        if row is None or datetime.now(timezone.utc).replace(tzinfo=None) - row[0] > timedelta(minutes=max_age_minutes):
            return None
        return json.loads(row[1])

    def save_options(self, symbol: str, payload: dict) -> None:
        self.connection.execute("DELETE FROM option_chains WHERE symbol = ?", [symbol])
        self.connection.execute(
            "INSERT INTO option_chains VALUES (?, ?, ?)",
            [symbol, datetime.now(timezone.utc).replace(tzinfo=None), json.dumps(payload)],
        )

    def save_strategy(self, instruction: str, definition: dict, provider: str, strategy_yaml: str) -> dict:
        fingerprint = json.dumps({"instruction": instruction.strip().lower(), "yaml": strategy_yaml}, sort_keys=True)
        row = self.connection.execute(
            "SELECT strategy_id, created_at FROM strategy_catalogue WHERE fingerprint = ?", [fingerprint]
        ).fetchone()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        strategy_id, created_at = (row[0], row[1]) if row else (str(uuid4()), now)
        self.connection.execute("DELETE FROM strategy_catalogue WHERE fingerprint = ?", [fingerprint])
        self.connection.execute(
            """INSERT INTO strategy_catalogue
               (strategy_id, fingerprint, instruction, name, description, strategy_type, direction, parameters, provider, strategy_yaml, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [strategy_id, fingerprint, instruction, definition["name"], definition["description"], definition["strategy_type"], definition["direction"], json.dumps(definition["parameters"]), provider, strategy_yaml, created_at, now],
        )
        return {"id": strategy_id, "createdAt": created_at.isoformat(), "updatedAt": now.isoformat(), **definition, "provider": provider, "instruction": instruction, "strategyYaml": strategy_yaml}

    def list_strategies(self) -> list[dict]:
        rows = self.connection.execute(
            """SELECT strategy_id, instruction, name, description, strategy_type, direction, parameters, provider, strategy_yaml, created_at, updated_at
               FROM strategy_catalogue ORDER BY updated_at DESC"""
        ).fetchall()
        return [{
            "id": row[0], "instruction": row[1], "name": row[2], "description": row[3],
            "strategy_type": row[4], "direction": row[5], "parameters": json.loads(row[6]),
            "provider": row[7], "strategyYaml": row[8], "createdAt": row[9].isoformat(), "updatedAt": row[10].isoformat(),
        } for row in rows]

    def get_strategy(self, strategy_id: str) -> dict | None:
        return next((strategy for strategy in self.list_strategies() if strategy["id"] == strategy_id), None)

    def save_backtest(self, strategy_id: str, ticker: str, window: str, metrics: dict, trades: list[dict]) -> str:
        run_id, now = str(uuid4()), datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.execute(
            "INSERT INTO backtest_runs VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, strategy_id, ticker, window, json.dumps(metrics), now],
        )
        if trades:
            rows = [[run_id, number + 1, trade["entryDate"], trade["entryPrice"], trade["exitDate"], trade["exitPrice"], trade["side"], trade["pnl"], trade["pnlPercent"]] for number, trade in enumerate(trades)]
            self.connection.executemany("INSERT INTO backtest_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        return run_id
