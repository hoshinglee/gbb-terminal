from __future__ import annotations

from datetime import datetime, timezone

import duckdb


CURRENT_SCHEMA_VERSION = 3


def record_schema_version(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL
        )
    """)
    exists = connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", [CURRENT_SCHEMA_VERSION]).fetchone()
    if not exists:
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?)",
            [CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).replace(tzinfo=None)],
        )
