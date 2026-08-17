from __future__ import annotations

from datetime import datetime, timezone

import duckdb


CURRENT_SCHEMA_VERSION = 16


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


def apply_earnings_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS earnings_events (
            event_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            cik VARCHAR NOT NULL,
            ticker VARCHAR NOT NULL,
            fiscal_year INTEGER,
            fiscal_period VARCHAR,
            period_end DATE NOT NULL,
            announcement_at TIMESTAMP,
            announcement_date DATE NOT NULL,
            session VARCHAR NOT NULL CHECK (session IN ('before_open', 'after_close', 'intraday', 'unknown')),
            timing_quality VARCHAR NOT NULL CHECK (timing_quality IN ('exact', 'date_only')),
            evidence JSON NOT NULL,
            reported_metrics JSON NOT NULL,
            guidance_metadata JSON NOT NULL,
            model_version VARCHAR NOT NULL,
            warnings JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS earnings_company_date_index ON earnings_events(company_id, announcement_date)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS earnings_reactions (
            event_id VARCHAR NOT NULL REFERENCES earnings_events(event_id),
            benchmark_ticker VARCHAR NOT NULL,
            anchor_session DATE,
            prior_session DATE,
            opening_gap DOUBLE,
            abnormal_volume DOUBLE,
            volume_percentile DOUBLE,
            windows JSON NOT NULL,
            path JSON NOT NULL,
            engine_version VARCHAR NOT NULL,
            warnings JSON NOT NULL,
            computed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (event_id, benchmark_ticker, engine_version)
        )
    """)


def apply_evidence_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence_documents (
            document_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            source VARCHAR NOT NULL,
            dataset VARCHAR NOT NULL,
            document_type VARCHAR NOT NULL CHECK (
                document_type IN ('10-k', '10-q', '8-k', 'earnings_release', 'annual_report',
                                  'investor_presentation', 'other')
            ),
            external_id VARCHAR NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            supersedes_document_id VARCHAR,
            title VARCHAR,
            form VARCHAR,
            accession_number VARCHAR,
            source_url VARCHAR NOT NULL,
            filed_at TIMESTAMP,
            published_at TIMESTAMP,
            known_at TIMESTAMP NOT NULL,
            retrieved_at TIMESTAMP NOT NULL,
            content_hash VARCHAR NOT NULL,
            mime_type VARCHAR NOT NULL,
            parse_status VARCHAR NOT NULL CHECK (parse_status IN ('pending', 'parsed', 'failed')),
            parse_error VARCHAR,
            source_metadata JSON NOT NULL,
            quality_warnings JSON NOT NULL,
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            UNIQUE (company_id, source, external_id, content_hash)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS evidence_document_company_known_index ON evidence_documents(company_id, known_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS evidence_document_source_identity_index ON evidence_documents(source, external_id)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence_spans (
            span_id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES evidence_documents(document_id),
            span_hash VARCHAR NOT NULL,
            exact_text VARCHAR NOT NULL,
            section VARCHAR,
            page_number INTEGER,
            start_offset INTEGER,
            end_offset INTEGER,
            context_before VARCHAR,
            context_after VARCHAR,
            extraction_method VARCHAR NOT NULL,
            extracted_at TIMESTAMP NOT NULL,
            source_metadata JSON NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CHECK (page_number IS NULL OR page_number >= 1),
            CHECK ((start_offset IS NULL AND end_offset IS NULL) OR
                   (start_offset >= 0 AND end_offset > start_offset)),
            UNIQUE (document_id, span_hash)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS evidence_span_document_index ON evidence_spans(document_id)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence_claim_links (
            claim_type VARCHAR NOT NULL,
            claim_id VARCHAR NOT NULL,
            span_id VARCHAR NOT NULL REFERENCES evidence_spans(span_id),
            evidence_role VARCHAR NOT NULL CHECK (evidence_role IN ('support', 'context', 'contradiction')),
            created_at TIMESTAMP NOT NULL,
            PRIMARY KEY (claim_type, claim_id, span_id, evidence_role)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS evidence_claim_index ON evidence_claim_links(claim_type, claim_id)"
    )


def apply_relationship_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS business_relationships (
            relationship_id VARCHAR PRIMARY KEY,
            source_company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            normalized_counterparty_name VARCHAR NOT NULL,
            raw_counterparty_name VARCHAR NOT NULL,
            relationship_type VARCHAR NOT NULL CHECK (
                relationship_type IN ('supplier', 'customer', 'manufacturer_foundry', 'distributor',
                                      'strategic_partner', 'competitor', 'customer_concentration',
                                      'supplier_concentration')
            ),
            direction VARCHAR NOT NULL CHECK (
                direction IN ('upstream', 'downstream', 'bidirectional', 'market')
            ),
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            UNIQUE (source_company_id, normalized_counterparty_name, relationship_type, direction)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS relationship_source_index ON business_relationships(source_company_id)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS relationship_observations (
            observation_id VARCHAR PRIMARY KEY,
            relationship_id VARCHAR NOT NULL REFERENCES business_relationships(relationship_id),
            target_company_id VARCHAR REFERENCES companies(company_id),
            exposure_value DOUBLE,
            exposure_unit VARCHAR,
            valid_from DATE,
            valid_to DATE,
            known_at TIMESTAMP NOT NULL,
            extraction_method VARCHAR NOT NULL,
            confidence VARCHAR NOT NULL CHECK (
                confidence IN ('disclosed', 'strongly_inferred', 'inferred')
            ),
            observation_kind VARCHAR NOT NULL CHECK (
                observation_kind IN ('extracted', 'human_override')
            ),
            supersedes_observation_id VARCHAR,
            correction_note VARCHAR,
            created_at TIMESTAMP NOT NULL,
            CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
            CHECK ((exposure_value IS NULL AND exposure_unit IS NULL) OR
                   (exposure_value IS NOT NULL AND exposure_unit IS NOT NULL))
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS relationship_observation_edge_index ON relationship_observations(relationship_id, known_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS relationship_observation_target_index ON relationship_observations(target_company_id, known_at)"
    )


def apply_operations_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operating_metric_definitions (
            definition_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            category VARCHAR NOT NULL CHECK (category IN ('segment', 'geography', 'kpi')),
            definition_key VARCHAR NOT NULL,
            label VARCHAR NOT NULL,
            measure VARCHAR NOT NULL,
            unit VARCHAR NOT NULL,
            value_type VARCHAR NOT NULL CHECK (
                value_type IN ('currency', 'percentage', 'count', 'ratio', 'duration', 'other')
            ),
            reporting_basis VARCHAR NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            valid_from DATE,
            valid_to DATE,
            supersedes_definition_id VARCHAR,
            description VARCHAR,
            known_at TIMESTAMP NOT NULL,
            extraction_method VARCHAR NOT NULL,
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
            UNIQUE (company_id, category, definition_key, reporting_basis, version)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS operating_definition_company_index ON operating_metric_definitions(company_id, category, known_at)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operating_metric_observations (
            observation_id VARCHAR PRIMARY KEY,
            definition_id VARCHAR NOT NULL REFERENCES operating_metric_definitions(definition_id),
            period_start DATE,
            period_end DATE NOT NULL,
            fiscal_year INTEGER,
            fiscal_period VARCHAR,
            value DOUBLE NOT NULL,
            unit VARCHAR NOT NULL,
            known_at TIMESTAMP NOT NULL,
            extraction_method VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CHECK (period_start IS NULL OR period_end >= period_start)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS operating_observation_definition_index ON operating_metric_observations(definition_id, period_end, known_at)"
    )


def apply_guidance_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS guidance_statements (
            statement_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            statement_type VARCHAR NOT NULL CHECK (
                statement_type IN ('financial_guidance', 'strategic_commitment', 'kpi_target', 'risk_constraint')
            ),
            topic VARCHAR NOT NULL,
            metric_id VARCHAR,
            statement_text VARCHAR NOT NULL,
            value_kind VARCHAR NOT NULL CHECK (
                value_kind IN ('numeric_range', 'numeric_point', 'qualitative')
            ),
            comparison VARCHAR NOT NULL CHECK (
                comparison IN ('within_range', 'at_least', 'at_most', 'approximately', 'not_applicable')
            ),
            lower_bound DOUBLE,
            upper_bound DOUBLE,
            point_value DOUBLE,
            unit VARCHAR,
            applicable_period_start DATE,
            applicable_period_end DATE,
            fiscal_year INTEGER,
            fiscal_period VARCHAR,
            issued_at TIMESTAMP NOT NULL,
            known_at TIMESTAMP NOT NULL,
            extraction_method VARCHAR NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            supersedes_statement_id VARCHAR,
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CHECK (applicable_period_start IS NULL OR applicable_period_end IS NULL OR
                   applicable_period_end >= applicable_period_start)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS guidance_statement_company_index ON guidance_statements(company_id, known_at, topic)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS guidance_evaluations (
            evaluation_id VARCHAR PRIMARY KEY,
            statement_id VARCHAR NOT NULL REFERENCES guidance_statements(statement_id),
            status VARCHAR NOT NULL CHECK (
                status IN ('open', 'delivered', 'partially_delivered', 'missed', 'withdrawn',
                           'superseded', 'unknown')
            ),
            evaluated_at TIMESTAMP NOT NULL,
            known_at TIMESTAMP NOT NULL,
            method VARCHAR NOT NULL CHECK (method IN ('system', 'rule_based', 'manual', 'interpretive')),
            actual_value DOUBLE,
            actual_unit VARCHAR,
            source_fact_ids JSON NOT NULL,
            resulting_statement_id VARCHAR,
            note VARCHAR,
            created_at TIMESTAMP NOT NULL,
            CHECK ((actual_value IS NULL AND actual_unit IS NULL) OR
                   (actual_value IS NOT NULL AND actual_unit IS NOT NULL))
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS guidance_evaluation_statement_index ON guidance_evaluations(statement_id, known_at)"
    )


def apply_intelligence_collection_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS evidence_document_contents (
            document_id VARCHAR PRIMARY KEY REFERENCES evidence_documents(document_id),
            content BLOB NOT NULL,
            encoding VARCHAR,
            parser_version VARCHAR,
            stored_at TIMESTAMP NOT NULL,
            parsed_at TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_refresh_runs (
            refresh_id VARCHAR PRIMARY KEY,
            company_id VARCHAR NOT NULL REFERENCES companies(company_id),
            ticker VARCHAR NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed', 'cancelled')),
            request JSON NOT NULL,
            documents_discovered INTEGER NOT NULL,
            documents_downloaded INTEGER NOT NULL,
            documents_unchanged INTEGER NOT NULL,
            documents_parsed INTEGER NOT NULL,
            documents_failed INTEGER NOT NULL,
            relationship_count INTEGER NOT NULL,
            operating_observation_count INTEGER NOT NULL,
            guidance_statement_count INTEGER NOT NULL,
            coverage JSON NOT NULL,
            warnings JSON NOT NULL,
            model_version VARCHAR NOT NULL,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS intelligence_refresh_company_index ON intelligence_refresh_runs(company_id, started_at)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_refresh_items (
            item_id VARCHAR PRIMARY KEY,
            refresh_id VARCHAR NOT NULL REFERENCES intelligence_refresh_runs(refresh_id),
            external_id VARCHAR NOT NULL,
            source_url VARCHAR,
            accession_number VARCHAR,
            form VARCHAR,
            status VARCHAR NOT NULL CHECK (
                status IN ('discovered', 'unchanged', 'downloaded', 'parsed', 'no_disclosure',
                           'parse_failed', 'extraction_failed', 'provider_failed', 'unsupported_format')
            ),
            document_id VARCHAR REFERENCES evidence_documents(document_id),
            reason VARCHAR,
            created_at TIMESTAMP NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS intelligence_refresh_item_run_index ON intelligence_refresh_items(refresh_id, created_at)"
    )


def apply_universe_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS universe_snapshots (
            snapshot_id VARCHAR PRIMARY KEY,
            universe_key VARCHAR NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            as_of_date DATE NOT NULL,
            source VARCHAR NOT NULL,
            source_url VARCHAR NOT NULL,
            known_at TIMESTAMP NOT NULL,
            retrieved_at TIMESTAMP NOT NULL,
            content_hash VARCHAR NOT NULL,
            constituent_count INTEGER NOT NULL,
            quality_warnings JSON NOT NULL,
            metadata JSON NOT NULL,
            UNIQUE (universe_key, version),
            UNIQUE (universe_key, content_hash)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS universe_snapshot_latest_index ON universe_snapshots(universe_key, version)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS universe_constituents (
            snapshot_id VARCHAR NOT NULL REFERENCES universe_snapshots(snapshot_id),
            symbol VARCHAR NOT NULL,
            source_symbol VARCHAR NOT NULL,
            company_name VARCHAR NOT NULL,
            sector VARCHAR NOT NULL,
            sub_industry VARCHAR NOT NULL,
            cik VARCHAR NOT NULL,
            date_added DATE,
            company_id VARCHAR REFERENCES companies(company_id),
            metadata JSON NOT NULL,
            PRIMARY KEY (snapshot_id, symbol)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS universe_constituent_sector_index ON universe_constituents(snapshot_id, sector, symbol)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS universe_refresh_runs (
            refresh_id VARCHAR PRIMARY KEY,
            universe_key VARCHAR NOT NULL,
            snapshot_id VARCHAR NOT NULL REFERENCES universe_snapshots(snapshot_id),
            status VARCHAR NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed', 'cancelled')),
            profile VARCHAR NOT NULL,
            request JSON NOT NULL,
            total_count INTEGER NOT NULL,
            completed_count INTEGER NOT NULL,
            partial_count INTEGER NOT NULL,
            skipped_count INTEGER NOT NULL,
            failed_count INTEGER NOT NULL,
            cancelled_count INTEGER NOT NULL,
            warnings JSON NOT NULL,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS universe_refresh_latest_index ON universe_refresh_runs(universe_key, started_at)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS universe_refresh_items (
            item_id VARCHAR PRIMARY KEY,
            refresh_id VARCHAR NOT NULL REFERENCES universe_refresh_runs(refresh_id),
            symbol VARCHAR NOT NULL,
            company_id VARCHAR REFERENCES companies(company_id),
            status VARCHAR NOT NULL CHECK (
                status IN ('queued', 'running', 'completed', 'partial', 'failed', 'skipped', 'cancelled')
            ),
            stage VARCHAR NOT NULL,
            attempt_count INTEGER NOT NULL,
            market_cap DOUBLE,
            daily_change_percent DOUBLE,
            price_observed_at TIMESTAMP,
            price_status VARCHAR,
            financial_metric_count INTEGER NOT NULL,
            valuation_point_count INTEGER NOT NULL,
            earnings_event_count INTEGER NOT NULL,
            warnings JSON NOT NULL,
            error VARCHAR,
            updated_at TIMESTAMP NOT NULL,
            UNIQUE (refresh_id, symbol)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS universe_refresh_item_status_index ON universe_refresh_items(refresh_id, status, symbol)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS universe_company_cache (
            universe_key VARCHAR NOT NULL,
            snapshot_id VARCHAR NOT NULL REFERENCES universe_snapshots(snapshot_id),
            symbol VARCHAR NOT NULL,
            company_id VARCHAR REFERENCES companies(company_id),
            company_name VARCHAR NOT NULL,
            sector VARCHAR NOT NULL,
            sub_industry VARCHAR NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('completed', 'partial', 'failed', 'skipped')),
            price DOUBLE,
            daily_change_percent DOUBLE,
            market_cap DOUBLE,
            market_cap_source VARCHAR NOT NULL,
            observation_timestamp TIMESTAMP,
            known_at TIMESTAMP,
            retrieved_at TIMESTAMP NOT NULL,
            financial_metric_count INTEGER NOT NULL,
            valuation_point_count INTEGER NOT NULL,
            earnings_event_count INTEGER NOT NULL,
            quality_warnings JSON NOT NULL,
            last_success_at TIMESTAMP,
            PRIMARY KEY (universe_key, symbol)
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS universe_cache_sector_index ON universe_company_cache(universe_key, sector, daily_change_percent)"
    )


def record_schema_version(connection: duckdb.DuckDBPyConnection) -> None:
    apply_company_identity_schema(connection)
    apply_financial_fact_schema(connection)
    apply_valuation_schema(connection)
    apply_earnings_schema(connection)
    apply_evidence_schema(connection)
    apply_relationship_schema(connection)
    apply_operations_schema(connection)
    apply_guidance_schema(connection)
    apply_intelligence_collection_schema(connection)
    apply_universe_schema(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL
        )
    """)
    exists = connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", [CURRENT_SCHEMA_VERSION]).fetchone()
    if not exists:
        remove_relationship_extractor_v2_candidates(connection)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?)",
            [CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).replace(tzinfo=None)],
        )


def remove_relationship_extractor_v2_candidates(connection: duckdb.DuckDBPyConnection) -> None:
    extraction_method = "deterministic_relationship_rules_v2"
    connection.execute(
        """DELETE FROM evidence_claim_links
           WHERE claim_type = 'relationship'
             AND claim_id IN (
                 SELECT observation_id FROM relationship_observations WHERE extraction_method = ?
             )""",
        [extraction_method],
    )
    connection.execute(
        "DELETE FROM relationship_observations WHERE extraction_method = ?",
        [extraction_method],
    )
    connection.execute(
        """DELETE FROM business_relationships
           WHERE NOT EXISTS (
               SELECT 1 FROM relationship_observations
               WHERE relationship_observations.relationship_id = business_relationships.relationship_id
           )"""
    )
