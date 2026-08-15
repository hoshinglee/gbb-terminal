from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha256

import duckdb

from .evidence_models import EvidenceClaimLinkCreate
from .evidence_repository import EvidenceRepository
from .guidance_models import (
    GUIDANCE_MODEL_VERSION,
    GuidanceEvaluation,
    GuidanceEvaluationCreate,
    GuidanceEvaluationMethod,
    GuidanceQuery,
    GuidanceStatement,
    GuidanceStatementCreate,
    GuidanceStatus,
)


STATEMENT_COLUMNS = """statement_id, company_id, statement_type, topic, metric_id, statement_text,
    value_kind, comparison, lower_bound, upper_bound, point_value, unit, applicable_period_start,
    applicable_period_end, fiscal_year, fiscal_period, issued_at, known_at, extraction_method,
    revision, supersedes_statement_id, model_version, created_at"""

EVALUATION_COLUMNS = """evaluation_id, statement_id, status, evaluated_at, known_at, method, actual_value,
    actual_unit, source_fact_ids, resulting_statement_id, note, created_at"""


class GuidanceRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection, evidence: EvidenceRepository) -> None:
        self.connection = connection
        self.evidence = evidence

    def save_statement(self, command: GuidanceStatementCreate) -> GuidanceStatement:
        self._require_company(command.company_id)
        spans = self._require_evidence(command.company_id, command.evidence_span_ids, command.known_at)
        normalized_statement = self._normalize_text(command.statement_text)
        if not any(normalized_statement in self._normalize_text(span.exact_text) for span in spans):
            raise ValueError("Guidance statement_text must be present in at least one linked evidence span.")
        prior = None
        revision = 1
        if command.supersedes_statement_id:
            prior = self.get_statement(command.supersedes_statement_id)
            if prior.company_id != command.company_id:
                raise ValueError("Guidance may supersede only a statement from the same company.")
            if prior.statement_type != command.statement_type or prior.metric_id != command.metric_id:
                raise ValueError("Guidance revisions must retain statement type and metric identity.")
            if self._normalize_text(prior.topic) != self._normalize_text(command.topic):
                raise ValueError("Guidance revisions must retain the same topic.")
            revision = prior.revision + 1
        statement_id = self._statement_id(command, revision)
        existing = self._optional_statement(statement_id)
        if existing:
            for span in spans:
                self._link("guidance_statement", statement_id, span.span_id)
            return existing
        now = self._utc_now()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO guidance_statements
                   (statement_id, company_id, statement_type, topic, metric_id, statement_text, value_kind,
                    comparison, lower_bound, upper_bound, point_value, unit, applicable_period_start,
                    applicable_period_end, fiscal_year, fiscal_period, issued_at, known_at, extraction_method,
                    revision, supersedes_statement_id, model_version, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    statement_id,
                    command.company_id,
                    command.statement_type.value,
                    command.topic,
                    command.metric_id,
                    command.statement_text,
                    command.value_kind.value,
                    command.comparison.value,
                    command.lower_bound,
                    command.upper_bound,
                    command.point_value,
                    command.unit,
                    command.applicable_period_start,
                    command.applicable_period_end,
                    command.fiscal_year,
                    command.fiscal_period,
                    self._naive_utc(command.issued_at),
                    self._naive_utc(command.known_at),
                    command.extraction_method,
                    revision,
                    command.supersedes_statement_id,
                    GUIDANCE_MODEL_VERSION,
                    now,
                ],
            )
            for span in spans:
                self._link("guidance_statement", statement_id, span.span_id)
            if prior:
                self._insert_evaluation(
                    GuidanceEvaluationCreate(
                        statement_id=prior.statement_id,
                        status=GuidanceStatus.SUPERSEDED,
                        evaluated_at=command.issued_at,
                        known_at=command.known_at,
                        method=GuidanceEvaluationMethod.SYSTEM,
                        evidence_span_ids=command.evidence_span_ids,
                        resulting_statement_id=statement_id,
                        note=f"Superseded by revision {revision}.",
                    ),
                    prior.company_id,
                    spans,
                )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_statement(statement_id)

    def save_evaluation(self, command: GuidanceEvaluationCreate) -> GuidanceEvaluation:
        statement = self.get_statement(command.statement_id)
        if command.known_at < statement.known_at:
            raise ValueError("Guidance evaluation known_at cannot precede its statement.")
        if command.method == GuidanceEvaluationMethod.RULE_BASED and command.status in {
            GuidanceStatus.DELIVERED,
            GuidanceStatus.MISSED,
            GuidanceStatus.PARTIALLY_DELIVERED,
        } and command.actual_value is None:
            raise ValueError("Rule-based outcome evaluation requires an actual value.")
        spans = self._require_evidence(statement.company_id, command.evidence_span_ids, command.known_at)
        self._require_source_facts(statement.company_id, command.source_fact_ids, command.known_at)
        self.connection.execute("BEGIN TRANSACTION")
        try:
            evaluation = self._insert_evaluation(command, statement.company_id, spans)
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return evaluation

    def get_statement(self, statement_id: str) -> GuidanceStatement:
        statement = self._optional_statement(statement_id)
        if statement is None:
            raise LookupError(f"No guidance statement exists for statement_id {statement_id}.")
        return statement

    def get_evaluation(self, evaluation_id: str) -> GuidanceEvaluation | None:
        row = self.connection.execute(
            f"SELECT {EVALUATION_COLUMNS} FROM guidance_evaluations WHERE evaluation_id = ?",
            [evaluation_id],
        ).fetchone()
        return self._row_to_evaluation(row) if row else None

    def list_statements(self, company_id: str, query: GuidanceQuery) -> list[GuidanceStatement]:
        conditions = ["company_id = ?"]
        parameters: list[object] = [company_id]
        if query.statement_types:
            conditions.append(f"statement_type IN ({','.join('?' for _ in query.statement_types)})")
            parameters.extend(statement_type.value for statement_type in query.statement_types)
        if query.as_of:
            conditions.append("known_at <= ?")
            parameters.append(self._naive_utc(query.as_of))
        rows = self.connection.execute(
            f"""SELECT {STATEMENT_COLUMNS} FROM guidance_statements
                WHERE {' AND '.join(conditions)} ORDER BY known_at, revision, created_at""",
            parameters,
        ).fetchall()
        return [self._row_to_statement(row) for row in rows]

    def list_evaluations(self, statement_id: str, as_of: datetime) -> list[GuidanceEvaluation]:
        rows = self.connection.execute(
            f"""SELECT {EVALUATION_COLUMNS} FROM guidance_evaluations
                WHERE statement_id = ? AND known_at <= ? ORDER BY known_at, created_at""",
            [statement_id, self._naive_utc(as_of)],
        ).fetchall()
        return [self._row_to_evaluation(row) for row in rows]

    def count_statements(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM guidance_statements").fetchone()[0])

    def count_evaluations(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM guidance_evaluations").fetchone()[0])

    def _insert_evaluation(
        self,
        command: GuidanceEvaluationCreate,
        company_id: str,
        spans,
    ) -> GuidanceEvaluation:
        evaluation_id = self._evaluation_id(command)
        existing = self.get_evaluation(evaluation_id)
        if existing is None:
            self.connection.execute(
                """INSERT INTO guidance_evaluations
                   (evaluation_id, statement_id, status, evaluated_at, known_at, method, actual_value,
                    actual_unit, source_fact_ids, resulting_statement_id, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    evaluation_id,
                    command.statement_id,
                    command.status.value,
                    self._naive_utc(command.evaluated_at),
                    self._naive_utc(command.known_at),
                    command.method.value,
                    command.actual_value,
                    command.actual_unit,
                    json.dumps(command.source_fact_ids),
                    command.resulting_statement_id,
                    command.note,
                    self._utc_now(),
                ],
            )
        for span in spans:
            self._link("guidance_evaluation", evaluation_id, span.span_id)
        return self.get_evaluation(evaluation_id)

    def _optional_statement(self, statement_id: str) -> GuidanceStatement | None:
        row = self.connection.execute(
            f"SELECT {STATEMENT_COLUMNS} FROM guidance_statements WHERE statement_id = ?",
            [statement_id],
        ).fetchone()
        return self._row_to_statement(row) if row else None

    def _require_company(self, company_id: str) -> None:
        if self.connection.execute("SELECT 1 FROM companies WHERE company_id = ?", [company_id]).fetchone() is None:
            raise LookupError(f"No canonical company exists for company_id {company_id}.")

    def _require_evidence(self, company_id: str, span_ids: list[str], known_at: datetime):
        spans = []
        for span_id in span_ids:
            span = self.evidence.get_span(span_id)
            document = self.evidence.get_document(span.document_id) if span else None
            if span is None or document is None:
                raise LookupError(f"No evidence span exists for span_id {span_id}.")
            if document.company_id != company_id:
                raise ValueError("Guidance evidence must belong to the selected company.")
            if document.known_at > known_at:
                raise ValueError("Guidance known_at cannot precede its source evidence.")
            spans.append(span)
        return spans

    def _require_source_facts(self, company_id: str, fact_ids: list[str], known_at: datetime) -> None:
        for fact_id in fact_ids:
            row = self.connection.execute(
                "SELECT company_id, known_at FROM sec_financial_facts WHERE fact_id = ?",
                [fact_id],
            ).fetchone()
            if row is None:
                raise LookupError(f"No SEC financial fact exists for fact_id {fact_id}.")
            if row[0] != company_id:
                raise ValueError("Guidance outcome source facts must belong to the selected company.")
            if self._aware_utc(row[1]) > known_at.astimezone(timezone.utc):
                raise ValueError("Guidance evaluation known_at cannot precede an outcome source fact.")

    def _link(self, claim_type: str, claim_id: str, span_id: str) -> None:
        self.evidence.link_claim(
            EvidenceClaimLinkCreate(
                claim_type=claim_type,
                claim_id=claim_id,
                span_id=span_id,
            )
        )

    @staticmethod
    def _statement_id(command: GuidanceStatementCreate, revision: int) -> str:
        payload = {
            **command.model_dump(mode="json", exclude={"evidence_span_ids"}),
            "revision": revision,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _evaluation_id(command: GuidanceEvaluationCreate) -> str:
        payload = command.model_dump(mode="json", exclude={"evidence_span_ids"})
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    @staticmethod
    def _row_to_statement(row: tuple) -> GuidanceStatement:
        return GuidanceStatement(
            statement_id=row[0],
            company_id=row[1],
            statement_type=row[2],
            topic=row[3],
            metric_id=row[4],
            statement_text=row[5],
            value_kind=row[6],
            comparison=row[7],
            lower_bound=row[8],
            upper_bound=row[9],
            point_value=row[10],
            unit=row[11],
            applicable_period_start=row[12],
            applicable_period_end=row[13],
            fiscal_year=row[14],
            fiscal_period=row[15],
            issued_at=GuidanceRepository._aware_utc(row[16]),
            known_at=GuidanceRepository._aware_utc(row[17]),
            extraction_method=row[18],
            revision=row[19],
            supersedes_statement_id=row[20],
            model_version=row[21],
            created_at=GuidanceRepository._aware_utc(row[22]),
        )

    @staticmethod
    def _row_to_evaluation(row: tuple) -> GuidanceEvaluation:
        return GuidanceEvaluation(
            evaluation_id=row[0],
            statement_id=row[1],
            status=row[2],
            evaluated_at=GuidanceRepository._aware_utc(row[3]),
            known_at=GuidanceRepository._aware_utc(row[4]),
            method=row[5],
            actual_value=row[6],
            actual_unit=row[7],
            source_fact_ids=json.loads(row[8]),
            resulting_statement_id=row[9],
            note=row[10],
            created_at=GuidanceRepository._aware_utc(row[11]),
        )

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
