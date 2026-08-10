from __future__ import annotations

from datetime import datetime, timezone

import duckdb


CURRENT_SCHEMA_VERSION = 8


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


def apply_financial_fact_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS sec_financial_facts (
            fact_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            cik VARCHAR NOT NULL,
            taxonomy VARCHAR NOT NULL,
            concept VARCHAR NOT NULL,
            label VARCHAR,
            description VARCHAR,
            value DOUBLE NOT NULL,
            raw_value VARCHAR NOT NULL,
            unit VARCHAR NOT NULL,
            period_start DATE,
            period_end DATE NOT NULL,
            fiscal_year INTEGER,
            fiscal_period VARCHAR,
            form VARCHAR NOT NULL,
            filed_date DATE NOT NULL,
            accepted_at TIMESTAMP,
            known_at TIMESTAMP NOT NULL,
            known_at_source VARCHAR NOT NULL,
            accession_number VARCHAR NOT NULL,
            frame VARCHAR,
            source VARCHAR NOT NULL,
            dataset VARCHAR NOT NULL,
            data_status VARCHAR NOT NULL,
            cached BOOLEAN NOT NULL,
            remaining_quota INTEGER,
            retrieved_at TIMESTAMP NOT NULL,
            quality_warnings JSON NOT NULL,
            source_metadata JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS sec_facts_company_period_index ON sec_financial_facts(company_id, period_end)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS sec_facts_company_known_at_index ON sec_financial_facts(company_id, known_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS sec_facts_concept_index ON sec_financial_facts(taxonomy, concept)"
    )


def apply_valuation_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS valuation_series (
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            ticker VARCHAR NOT NULL,
            valuation_date DATE NOT NULL,
            frequency VARCHAR NOT NULL CHECK (frequency IN ('daily', 'weekly')),
            metric_id VARCHAR NOT NULL,
            label VARCHAR NOT NULL,
            value DOUBLE,
            unit VARCHAR NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('available', 'nm', 'unavailable')),
            price DOUBLE NOT NULL,
            market_cap DOUBLE,
            enterprise_value DOUBLE,
            denominator_value DOUBLE,
            denominator_metric VARCHAR NOT NULL,
            fundamental_period_end DATE,
            fundamental_known_at TIMESTAMP,
            source_fact_ids JSON NOT NULL,
            price_source VARCHAR NOT NULL,
            warnings JSON NOT NULL,
            engine_version VARCHAR NOT NULL,
            computed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (company_id, ticker, valuation_date, frequency, metric_id, engine_version)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS valuation_company_date_index ON valuation_series(company_id, valuation_date)"
    )


def record_schema_version(connection: duckdb.DuckDBPyConnection) -> None:
    apply_company_identity_schema(connection)
    apply_financial_fact_schema(connection)
    apply_valuation_schema(connection)
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
