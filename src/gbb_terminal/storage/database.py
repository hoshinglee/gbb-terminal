from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from .migrations import record_schema_version


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
                strategy_key VARCHAR,
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
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS strategy_key VARCHAR")
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS strategy_yaml VARCHAR")
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS strategy_json JSON")
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS family VARCHAR")
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS template_id VARCHAR")
        self.connection.execute("ALTER TABLE strategy_catalogue ADD COLUMN IF NOT EXISTS template_version INTEGER")
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
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS research_runs (
                run_id VARCHAR PRIMARY KEY,
                strategy_id VARCHAR,
                strategy_json JSON NOT NULL,
                data_snapshot JSON NOT NULL,
                engine_version VARCHAR NOT NULL,
                validation JSON NOT NULL,
                tested_parameters JSON NOT NULL,
                results JSON NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS option_chain_snapshots (
                symbol VARCHAR NOT NULL,
                expiration DATE NOT NULL,
                snapshot_date DATE NOT NULL,
                known_at TIMESTAMP NOT NULL,
                source VARCHAR NOT NULL,
                payload JSON NOT NULL,
                PRIMARY KEY (symbol, expiration, snapshot_date)
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS option_positions (
                position_id VARCHAR PRIMARY KEY,
                owner_id VARCHAR,
                name VARCHAR NOT NULL,
                ticker VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                state JSON NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS option_position_events (
                event_id VARCHAR PRIMARY KEY,
                position_id VARCHAR NOT NULL,
                event_number INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                event_payload JSON NOT NULL,
                state_after JSON NOT NULL,
                created_at TIMESTAMP NOT NULL,
                UNIQUE (position_id, event_number)
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS local_jobs (
                job_id VARCHAR PRIMARY KEY,
                job_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                progress DOUBLE NOT NULL,
                request JSON NOT NULL,
                result JSON,
                error VARCHAR,
                cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS provider_cache (
                provider VARCHAR NOT NULL,
                dataset VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                observation_timestamp TIMESTAMP NOT NULL,
                known_at TIMESTAMP NOT NULL,
                retrieved_at TIMESTAMP NOT NULL,
                status VARCHAR NOT NULL,
                quality_warnings JSON NOT NULL,
                payload JSON NOT NULL,
                PRIMARY KEY (provider, dataset, symbol)
            )
        """)
        record_schema_version(self.connection)

    def load_history(self, symbol: str, period: str, max_age_minutes: int | None = 15) -> pd.DataFrame | None:
        newest = self.connection.execute(
            "SELECT max(fetched_at) FROM price_history WHERE symbol = ?", [symbol]
        ).fetchone()[0]
        if newest is None or (max_age_minutes is not None and datetime.now(timezone.utc).replace(tzinfo=None) - newest > timedelta(minutes=max_age_minutes)):
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

    def load_options(self, symbol: str, max_age_minutes: int | None = 15) -> dict | None:
        row = self.connection.execute(
            "SELECT fetched_at, payload FROM option_chains WHERE symbol = ?", [symbol]
        ).fetchone()
        if row is None or (max_age_minutes is not None and datetime.now(timezone.utc).replace(tzinfo=None) - row[0] > timedelta(minutes=max_age_minutes)):
            return None
        return json.loads(row[1])

    def save_options(self, symbol: str, payload: dict) -> None:
        self.connection.execute("DELETE FROM option_chains WHERE symbol = ?", [symbol])
        self.connection.execute(
            "INSERT INTO option_chains VALUES (?, ?, ?)",
            [symbol, datetime.now(timezone.utc).replace(tzinfo=None), json.dumps(payload)],
        )
        expiration = payload.get("expiration")
        if expiration:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            self.connection.execute(
                """INSERT OR REPLACE INTO option_chain_snapshots
                   (symbol, expiration, snapshot_date, known_at, source, payload)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [symbol, expiration, now.date(), now, payload.get("source", "Yahoo Finance"), json.dumps(payload)],
            )

    def save_strategy(
        self,
        instruction: str,
        definition: dict,
        provider: str,
        strategy_yaml: str,
        strategy_key: str,
        strategy_json: dict | None = None,
        family: str | None = None,
        template_id: str | None = None,
        template_version: int | None = None,
    ) -> dict:
        fingerprint = strategy_key
        row = self.connection.execute(
            "SELECT strategy_id, created_at FROM strategy_catalogue WHERE strategy_key = ?", [strategy_key]
        ).fetchone()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        strategy_id, created_at = (row[0], row[1]) if row else (str(uuid4()), now)
        values = [strategy_key, fingerprint, instruction, definition["name"], definition["description"], definition["strategy_type"], definition["direction"], json.dumps(definition["parameters"]), provider, strategy_yaml, now]
        if row:
            self.connection.execute(
                """UPDATE strategy_catalogue SET strategy_key = ?, fingerprint = ?, instruction = ?, name = ?,
                          description = ?, strategy_type = ?, direction = ?, parameters = ?, provider = ?,
                          strategy_yaml = ?, strategy_json = ?, family = ?, template_id = ?, template_version = ?,
                          updated_at = ? WHERE strategy_id = ?""",
                [*values[:-1], json.dumps(strategy_json) if strategy_json else None, family, template_id, template_version, now, strategy_id],
            )
        else:
            self.connection.execute(
                """INSERT INTO strategy_catalogue
                   (strategy_id, strategy_key, fingerprint, instruction, name, description, strategy_type, direction, parameters, provider, strategy_yaml, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [strategy_id, *values[:-1], created_at, now],
            )
            if strategy_json or family or template_id:
                self.connection.execute(
                    """UPDATE strategy_catalogue SET strategy_json = ?, family = ?, template_id = ?, template_version = ?
                       WHERE strategy_id = ?""",
                    [json.dumps(strategy_json) if strategy_json else None, family, template_id, template_version, strategy_id],
                )
        return {"id": strategy_id, "key": strategy_key, "createdAt": created_at.isoformat(), "updatedAt": now.isoformat(), **definition, "provider": provider, "instruction": instruction, "strategyYaml": strategy_yaml, "strategyJson": strategy_json, "family": family, "templateId": template_id, "templateVersion": template_version}

    def list_strategies(self) -> list[dict]:
        rows = self.connection.execute(
            """SELECT strategy_id, strategy_key, instruction, name, description, strategy_type, direction, parameters, provider, strategy_yaml, created_at, updated_at,
                      strategy_json, family, template_id, template_version
               FROM strategy_catalogue ORDER BY updated_at DESC"""
        ).fetchall()
        return [{
            "id": row[0], "key": row[1], "instruction": row[2], "name": row[3], "description": row[4],
            "strategy_type": row[5], "direction": row[6], "parameters": json.loads(row[7]),
            "provider": row[8], "strategyYaml": row[9], "createdAt": row[10].isoformat(), "updatedAt": row[11].isoformat(),
            "strategyJson": json.loads(row[12]) if row[12] else None, "family": row[13], "templateId": row[14], "templateVersion": row[15],
        } for row in rows]

    def get_strategy(self, strategy_id: str) -> dict | None:
        return next((strategy for strategy in self.list_strategies() if strategy["id"] == strategy_id), None)

    def deduplicate_strategies(self, strategy_resolver) -> int:
        groups: dict[str, list[tuple[dict, dict]]] = {}
        for item in self.list_strategies():
            resolved = strategy_resolver(item)
            groups.setdefault(resolved["key"], []).append((item, resolved))
        removed = 0
        self.connection.execute("BEGIN TRANSACTION")
        try:
            for strategy_key, records in groups.items():
                keeper, normalized = records[0]
                for duplicate, _ in records[1:]:
                    self.connection.execute("UPDATE backtest_runs SET strategy_id = ? WHERE strategy_id = ?", [keeper["id"], duplicate["id"]])
                    self.connection.execute("DELETE FROM strategy_catalogue WHERE strategy_id = ?", [duplicate["id"]])
                    removed += 1
                definition = normalized["definition"]
                self.connection.execute(
                    """UPDATE strategy_catalogue SET strategy_key = ?, fingerprint = ?, name = ?, description = ?,
                              strategy_type = ?, direction = ?, parameters = ?, strategy_yaml = ? WHERE strategy_id = ?""",
                    [strategy_key, strategy_key, definition["name"], definition["description"], definition["strategy_type"], definition["direction"], json.dumps(definition["parameters"]), normalized["strategy_yaml"], keeper["id"]],
                )
            self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS strategy_catalogue_key_index ON strategy_catalogue(strategy_key)")
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return removed

    def save_backtest(self, strategy_id: str, ticker: str, window: str, metrics: dict, trades: list[dict]) -> str:
        run_id, now = str(uuid4()), datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.execute(
            "INSERT INTO backtest_runs VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, strategy_id, ticker, window, json.dumps(metrics), now],
        )
        closed_trades = [trade for trade in trades if trade.get("status") == "Closed"]
        if closed_trades:
            rows = [[run_id, number + 1, trade["entryDate"], trade["entryPrice"], trade["exitDate"], trade["exitPrice"], trade["side"], trade["pnl"], trade["pnlPercent"]] for number, trade in enumerate(closed_trades)]
            self.connection.executemany("INSERT INTO backtest_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        return run_id

    def save_research_run(self, research_run: dict, strategy_id: str | None = None) -> str:
        created_at = datetime.fromisoformat(research_run["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        self.connection.execute(
            """INSERT INTO research_runs
               (run_id, strategy_id, strategy_json, data_snapshot, engine_version, validation,
                tested_parameters, results, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                research_run["run_id"],
                strategy_id,
                json.dumps(research_run["strategy"]),
                json.dumps(research_run["data_snapshot"]),
                research_run["engine_version"],
                json.dumps(research_run["validation"]),
                json.dumps(research_run["tested_parameters"]),
                json.dumps(research_run["results"]),
                created_at,
            ],
        )
        return research_run["run_id"]

    def get_research_run(self, run_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT run_id, strategy_id, strategy_json, data_snapshot, engine_version, validation,
                      tested_parameters, results, created_at
               FROM research_runs WHERE run_id = ?""",
            [run_id],
        ).fetchone()
        if row is None:
            return None
        return {
            "runId": row[0],
            "strategyId": row[1],
            "strategy": json.loads(row[2]),
            "dataSnapshot": json.loads(row[3]),
            "engineVersion": row[4],
            "validation": json.loads(row[5]),
            "testedParameters": json.loads(row[6]),
            "results": json.loads(row[7]),
            "createdAt": row[8].isoformat(),
        }

    def create_option_position(self, state: dict) -> dict:
        created_at = datetime.fromisoformat(state["opened_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        updated_at = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        self.connection.execute(
            """INSERT INTO option_positions
               (position_id, owner_id, name, ticker, status, state, created_at, updated_at)
               VALUES (?, NULL, ?, ?, ?, ?, ?, ?)""",
            [state["position_id"], state["name"], state["ticker"], state["status"], json.dumps(state), created_at, updated_at],
        )
        self.connection.execute(
            """INSERT INTO option_position_events
               (event_id, position_id, event_number, event_type, event_payload, state_after, created_at)
               VALUES (?, ?, 0, 'opened', ?, ?, ?)""",
            [str(uuid4()), state["position_id"], json.dumps({"type": "opened"}), json.dumps(state), created_at],
        )
        return state

    def get_option_position(self, position_id: str) -> dict | None:
        row = self.connection.execute("SELECT state FROM option_positions WHERE position_id = ?", [position_id]).fetchone()
        return json.loads(row[0]) if row else None

    def list_option_events(self, position_id: str) -> list[dict]:
        rows = self.connection.execute(
            """SELECT event_id, event_number, event_type, event_payload, state_after, created_at
               FROM option_position_events WHERE position_id = ? ORDER BY event_number""",
            [position_id],
        ).fetchall()
        return [{"eventId": row[0], "eventNumber": row[1], "eventType": row[2], "event": json.loads(row[3]), "stateAfter": json.loads(row[4]), "createdAt": row[5].isoformat()} for row in rows]

    def append_option_event(self, position_id: str, event: dict, state: dict) -> dict:
        row = self.connection.execute("SELECT coalesce(max(event_number), -1) + 1 FROM option_position_events WHERE position_id = ?", [position_id]).fetchone()
        event_number = int(row[0])
        created_at = datetime.fromisoformat(event["event_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO option_position_events
                   (event_id, position_id, event_number, event_type, event_payload, state_after, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [str(uuid4()), position_id, event_number, event["event_type"], json.dumps(event), json.dumps(state), created_at],
            )
            self.connection.execute(
                "UPDATE option_positions SET status = ?, state = ?, updated_at = ? WHERE position_id = ?",
                [state["status"], json.dumps(state), created_at, position_id],
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return state

    def save_provider_payload(self, metadata: dict, payload: dict | list) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO provider_cache
               (provider, dataset, symbol, observation_timestamp, known_at, retrieved_at, status,
                quality_warnings, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                metadata["source"], metadata["dataset"], metadata["symbol"],
                datetime.fromisoformat(metadata["observationTimestamp"]).replace(tzinfo=None),
                datetime.fromisoformat(metadata["knownAt"]).replace(tzinfo=None),
                datetime.fromisoformat(metadata["retrievedAt"]).replace(tzinfo=None),
                metadata["status"], json.dumps(metadata.get("qualityWarnings", [])), json.dumps(payload),
            ],
        )

    def load_provider_payload(self, provider: str, dataset: str, symbol: str) -> dict | None:
        row = self.connection.execute(
            """SELECT observation_timestamp, known_at, retrieved_at, status, quality_warnings, payload
               FROM provider_cache WHERE provider = ? AND dataset = ? AND symbol = ?""",
            [provider, dataset, symbol],
        ).fetchone()
        if row is None:
            return None
        return {
            "metadata": {"dataset": dataset, "symbol": symbol, "observationTimestamp": row[0].isoformat(), "knownAt": row[1].isoformat(), "retrievedAt": row[2].isoformat(), "status": row[3], "source": provider, "qualityWarnings": json.loads(row[4]), "cached": True},
            "data": json.loads(row[5]),
        }

    def create_job(self, job_type: str, request: dict) -> str:
        job_id, now = str(uuid4()), datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.execute(
            """INSERT INTO local_jobs
               (job_id, job_type, status, progress, request, result, error, cancel_requested, created_at, updated_at)
               VALUES (?, ?, 'running', 0, ?, NULL, NULL, FALSE, ?, ?)""",
            [job_id, job_type, json.dumps(request), now, now],
        )
        return job_id

    def update_job(self, job_id: str, progress: float | None = None, result: dict | None = None, error: str | None = None) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if result is not None:
            self.connection.execute("UPDATE local_jobs SET status = 'completed', progress = 1, result = ?, updated_at = ? WHERE job_id = ?", [json.dumps(result), now, job_id])
        elif error is not None:
            status = "cancelled" if "cancel" in error.lower() else "failed"
            self.connection.execute("UPDATE local_jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?", [status, error, now, job_id])
        elif progress is not None:
            self.connection.execute("UPDATE local_jobs SET progress = ?, updated_at = ? WHERE job_id = ?", [min(max(progress, 0), 1), now, job_id])

    def get_job(self, job_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT job_id, job_type, status, progress, request, result, error, cancel_requested, created_at, updated_at
               FROM local_jobs WHERE job_id = ?""",
            [job_id],
        ).fetchone()
        if row is None:
            return None
        return {"jobId": row[0], "jobType": row[1], "status": row[2], "progress": row[3], "request": json.loads(row[4]), "result": json.loads(row[5]) if row[5] else None, "error": row[6], "cancelRequested": row[7], "createdAt": row[8].isoformat(), "updatedAt": row[9].isoformat()}

    def request_job_cancellation(self, job_id: str) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.connection.execute("UPDATE local_jobs SET cancel_requested = TRUE, updated_at = ? WHERE job_id = ? AND status = 'running'", [now, job_id])
        row = self.connection.execute("SELECT cancel_requested FROM local_jobs WHERE job_id = ?", [job_id]).fetchone()
        return bool(row and row[0])

    def job_cancellation_requested(self, job_id: str) -> bool:
        row = self.connection.execute("SELECT cancel_requested FROM local_jobs WHERE job_id = ?", [job_id]).fetchone()
        return bool(row and row[0])
