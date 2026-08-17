from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb
import pandas as pd

from .fact_models import FinancialFact, FinancialFactQuery
from .models import CompanyProvenance


class FinancialFactRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def save_facts(self, facts: list[FinancialFact]) -> int:
        if not facts:
            return 0
        before = self.count_facts()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [self._fact_row(fact, now) for fact in facts]
        columns = [
            "fact_id",
            "company_id",
            "cik",
            "taxonomy",
            "concept",
            "label",
            "description",
            "value",
            "raw_value",
            "unit",
            "period_start",
            "period_end",
            "fiscal_year",
            "fiscal_period",
            "form",
            "filed_date",
            "accepted_at",
            "known_at",
            "known_at_source",
            "accession_number",
            "frame",
            "source",
            "dataset",
            "data_status",
            "cached",
            "remaining_quota",
            "retrieved_at",
            "quality_warnings",
            "source_metadata",
            "created_at",
            "updated_at",
        ]
        relation_name = f"incoming_sec_facts_{uuid4().hex}"
        self.connection.register(relation_name, pd.DataFrame(rows, columns=columns))
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                f"""INSERT OR IGNORE INTO sec_financial_facts ({", ".join(columns)})
                    SELECT {", ".join(columns)} FROM {relation_name}"""
            )
            self.connection.execute(
                f"""UPDATE sec_financial_facts AS existing
                    SET accepted_at = incoming.accepted_at,
                        known_at = incoming.known_at,
                        known_at_source = 'acceptance',
                        data_status = incoming.data_status,
                        cached = incoming.cached,
                        remaining_quota = incoming.remaining_quota,
                        retrieved_at = incoming.retrieved_at,
                        quality_warnings = incoming.quality_warnings,
                        source_metadata = incoming.source_metadata,
                        updated_at = incoming.updated_at
                    FROM {relation_name} AS incoming
                    WHERE existing.fact_id = incoming.fact_id
                      AND existing.known_at_source <> 'acceptance'
                      AND incoming.known_at_source = 'acceptance'"""
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        finally:
            self.connection.unregister(relation_name)
        return self.count_facts() - before

    def query_facts(self, company_id: str, query: FinancialFactQuery | None = None) -> list[FinancialFact]:
        request = query or FinancialFactQuery()
        conditions = ["company_id = ?"]
        parameters: list[object] = [company_id]
        if request.concepts:
            conditions.append(f"concept IN ({','.join('?' for _ in request.concepts)})")
            parameters.extend(request.concepts)
        if request.forms:
            conditions.append(f"form IN ({','.join('?' for _ in request.forms)})")
            parameters.extend(form.upper() for form in request.forms)
        if request.as_of is not None:
            conditions.append("known_at <= ?")
            parameters.append(request.as_of.astimezone(timezone.utc).replace(tzinfo=None))
        rows = self.connection.execute(
            f"""SELECT fact_id, company_id, cik, taxonomy, concept, label, description, value, raw_value, unit,
                       period_start, period_end, fiscal_year, fiscal_period, form, filed_date, accepted_at, known_at,
                       known_at_source, accession_number, frame, source, dataset, data_status, cached, remaining_quota,
                       retrieved_at, quality_warnings, source_metadata
                FROM sec_financial_facts WHERE {' AND '.join(conditions)}
                ORDER BY period_end, known_at, taxonomy, concept, unit""",
            parameters,
        ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def get_fact(self, fact_id: str) -> FinancialFact | None:
        row = self.connection.execute(
            """SELECT fact_id, company_id, cik, taxonomy, concept, label, description, value, raw_value, unit,
                      period_start, period_end, fiscal_year, fiscal_period, form, filed_date, accepted_at, known_at,
                      known_at_source, accession_number, frame, source, dataset, data_status, cached, remaining_quota,
                      retrieved_at, quality_warnings, source_metadata
               FROM sec_financial_facts WHERE fact_id = ?""",
            [fact_id],
        ).fetchone()
        return self._row_to_fact(row) if row else None

    def count_facts(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM sec_financial_facts").fetchone()[0])

    @staticmethod
    def _fact_row(fact: FinancialFact, now: datetime) -> list[object]:
        return [
            fact.fact_id,
            fact.company_id,
            fact.cik,
            fact.taxonomy,
            fact.concept,
            fact.label,
            fact.description,
            fact.value,
            fact.raw_value,
            fact.unit,
            fact.period_start,
            fact.period_end,
            fact.fiscal_year,
            fact.fiscal_period,
            fact.form.upper(),
            fact.filed_date,
            fact.accepted_at.astimezone(timezone.utc).replace(tzinfo=None) if fact.accepted_at else None,
            fact.provenance.known_at.astimezone(timezone.utc).replace(tzinfo=None),
            fact.known_at_source,
            fact.accession_number,
            fact.frame,
            fact.provenance.source,
            fact.provenance.dataset,
            fact.provenance.status,
            fact.provenance.cached,
            fact.provenance.remaining_quota,
            fact.provenance.retrieved_at.astimezone(timezone.utc).replace(tzinfo=None),
            json.dumps(fact.provenance.quality_warnings),
            json.dumps(fact.source_metadata),
            now,
            now,
        ]

    @staticmethod
    def _row_to_fact(row: tuple) -> FinancialFact:
        accepted_at = row[16].replace(tzinfo=timezone.utc) if row[16] else None
        known_at = row[17].replace(tzinfo=timezone.utc)
        retrieved_at = row[26].replace(tzinfo=timezone.utc)
        return FinancialFact(
            fact_id=row[0],
            company_id=row[1],
            cik=row[2],
            taxonomy=row[3],
            concept=row[4],
            label=row[5],
            description=row[6],
            value=row[7],
            raw_value=row[8],
            unit=row[9],
            period_start=row[10],
            period_end=row[11],
            fiscal_year=row[12],
            fiscal_period=row[13],
            form=row[14],
            filed_date=row[15],
            accepted_at=accepted_at,
            known_at_source=row[18],
            accession_number=row[19],
            frame=row[20],
            provenance=CompanyProvenance(
                source=row[21],
                dataset=row[22],
                observation_timestamp=datetime.combine(row[11], datetime.min.time(), tzinfo=timezone.utc),
                known_at=known_at,
                retrieved_at=retrieved_at,
                status=row[23],
                quality_warnings=json.loads(row[27]),
                remaining_quota=row[25],
                cached=row[24],
            ),
            source_metadata=json.loads(row[28]),
        )
