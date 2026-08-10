from __future__ import annotations

from datetime import datetime, timezone

import duckdb


CURRENT_SCHEMA_VERSION = 6


def apply_company_identity_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id VARCHAR PRIMARY KEY,
            cik VARCHAR UNIQUE NOT NULL,
            legal_name VARCHAR NOT NULL,
            sector VARCHAR,
            industry VARCHAR,
            fiscal_year_end VARCHAR,
            status VARCHAR NOT NULL CHECK (status IN ('active', 'inactive')),
            provenance JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS company_security_mappings (
            security_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            ticker VARCHAR NOT NULL,
            exchange VARCHAR,
            valid_from DATE NOT NULL,
            valid_to DATE,
            is_primary BOOLEAN NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('active', 'inactive')),
            provenance JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            CHECK (valid_to IS NULL OR valid_to >= valid_from),
            UNIQUE (company_id, ticker, exchange, valid_from)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS company_security_ticker_index ON company_security_mappings(ticker)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS company_security_company_index ON company_security_mappings(company_id)"
    )


def record_schema_version(connection: duckdb.DuckDBPyConnection) -> None:
    apply_company_identity_schema(connection)
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
