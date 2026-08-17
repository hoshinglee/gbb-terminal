from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256

import duckdb

from .evidence_models import EvidenceClaimLinkCreate
from .evidence_repository import EvidenceRepository
from .operations_models import (
    OPERATIONS_MODEL_VERSION,
    OperatingIntelligenceQuery,
    OperatingMetricDefinition,
    OperatingMetricDefinitionCreate,
    OperatingMetricObservation,
    OperatingMetricObservationCreate,
)


DEFINITION_COLUMNS = """definition_id, company_id, category, definition_key, label, measure, unit, value_type,
    reporting_basis, version, valid_from, valid_to, supersedes_definition_id, description, known_at,
    extraction_method, model_version, created_at"""

OBSERVATION_COLUMNS = """observation_id, definition_id, period_start, period_end, fiscal_year, fiscal_period,
    value, unit, known_at, extraction_method, created_at"""


class OperationsRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection, evidence: EvidenceRepository) -> None:
        self.connection = connection
        self.evidence = evidence

    def save_definition(self, command: OperatingMetricDefinitionCreate) -> OperatingMetricDefinition:
        self._require_company(command.company_id)
        spans = self._require_evidence(command.company_id, command.evidence_span_ids, command.known_at)
        prior = None
        if command.supersedes_definition_id:
            prior = self.get_definition(command.supersedes_definition_id)
            if prior.company_id != command.company_id or prior.category != command.category:
                raise ValueError("A definition may supersede only the same company's operating category.")
            if prior.definition_key != command.definition_key:
                raise ValueError("A superseding definition must retain its stable definition_key.")
            version = prior.version + 1
        else:
            version = 1
            existing = self.connection.execute(
                """SELECT definition_id FROM operating_metric_definitions
                   WHERE company_id = ? AND category = ? AND definition_key = ?
                   ORDER BY version DESC""",
                [command.company_id, command.category.value, command.definition_key],
            ).fetchall()
            if existing:
                for row in existing:
                    existing_definition = self.get_definition(row[0])
                    if self._same_definition(existing_definition, command):
                        if command.known_at < existing_definition.known_at:
                            raise ValueError(
                                "Earlier source timing for an existing definition requires an explicit historical correction."
                            )
                        for span in spans:
                            self._link("operating_definition", existing_definition.definition_id, span.span_id)
                        return existing_definition
                raise ValueError(
                    "A changed operating definition requires supersedes_definition_id so reorganizations remain visible."
                )
        definition_id = self._definition_id(command, version)
        existing_definition = self._optional_definition(definition_id)
        if existing_definition:
            for span in spans:
                self._link("operating_definition", definition_id, span.span_id)
            return existing_definition
        now = self._utc_now()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO operating_metric_definitions
                   (definition_id, company_id, category, definition_key, label, measure, unit, value_type,
                    reporting_basis, version, valid_from, valid_to, supersedes_definition_id, description,
                    known_at, extraction_method, model_version, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    definition_id,
                    command.company_id,
                    command.category.value,
                    command.definition_key,
                    command.label,
                    command.measure,
                    command.unit,
                    command.value_type.value,
                    command.reporting_basis,
                    version,
                    command.valid_from,
                    command.valid_to,
                    command.supersedes_definition_id,
                    command.description,
                    self._naive_utc(command.known_at),
                    command.extraction_method,
                    OPERATIONS_MODEL_VERSION,
                    now,
                ],
            )
            for span in spans:
                self._link("operating_definition", definition_id, span.span_id)
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_definition(definition_id)

    def save_observation(self, command: OperatingMetricObservationCreate) -> OperatingMetricObservation:
        definition = self.get_definition(command.definition_id)
        if command.unit != definition.unit:
            raise ValueError(
                f"Operating observation unit {command.unit} does not match definition unit {definition.unit}."
            )
        if command.known_at < definition.known_at:
            raise ValueError("Operating observation known_at cannot precede its definition.")
        spans = self._require_evidence(definition.company_id, command.evidence_span_ids, command.known_at)
        observation_id = self._observation_id(command)
        existing = self.get_observation(observation_id)
        if existing:
            for span in spans:
                self._link("operating_observation", observation_id, span.span_id)
            return existing
        now = self._utc_now()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO operating_metric_observations
                   (observation_id, definition_id, period_start, period_end, fiscal_year, fiscal_period,
                    value, unit, known_at, extraction_method, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    observation_id,
                    command.definition_id,
                    command.period_start,
                    command.period_end,
                    command.fiscal_year,
                    command.fiscal_period,
                    command.value,
                    command.unit,
                    self._naive_utc(command.known_at),
                    command.extraction_method,
                    now,
                ],
            )
            for span in spans:
                self._link("operating_observation", observation_id, span.span_id)
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self._require_observation(observation_id)

    def get_definition(self, definition_id: str) -> OperatingMetricDefinition:
        definition = self._optional_definition(definition_id)
        if definition is None:
            raise LookupError(f"No operating metric definition exists for definition_id {definition_id}.")
        return definition

    def get_observation(self, observation_id: str) -> OperatingMetricObservation | None:
        row = self.connection.execute(
            f"SELECT {OBSERVATION_COLUMNS} FROM operating_metric_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def list_definitions(
        self,
        company_id: str,
        query: OperatingIntelligenceQuery,
    ) -> list[OperatingMetricDefinition]:
        conditions = ["company_id = ?"]
        parameters: list[object] = [company_id]
        if query.categories:
            conditions.append(f"category IN ({','.join('?' for _ in query.categories)})")
            parameters.extend(category.value for category in query.categories)
        if query.as_of:
            conditions.append("known_at <= ?")
            parameters.append(self._naive_utc(query.as_of))
        rows = self.connection.execute(
            f"""SELECT {DEFINITION_COLUMNS} FROM operating_metric_definitions
                WHERE {' AND '.join(conditions)}
                ORDER BY category, reporting_basis, definition_key, version""",
            parameters,
        ).fetchall()
        return [self._row_to_definition(row) for row in rows]

    def latest_definition(
        self,
        company_id: str,
        category,
        definition_key: str,
    ) -> OperatingMetricDefinition | None:
        row = self.connection.execute(
            f"""SELECT {DEFINITION_COLUMNS} FROM operating_metric_definitions
                WHERE company_id = ? AND category = ? AND definition_key = ?
                ORDER BY version DESC, known_at DESC LIMIT 1""",
            [company_id, category.value, definition_key],
        ).fetchone()
        return self._row_to_definition(row) if row else None

    def list_observations(
        self,
        definition_id: str,
        as_of: datetime,
    ) -> list[OperatingMetricObservation]:
        rows = self.connection.execute(
            f"""SELECT {OBSERVATION_COLUMNS} FROM operating_metric_observations
                WHERE definition_id = ? AND known_at <= ?
                ORDER BY period_end, known_at, created_at""",
            [definition_id, self._naive_utc(as_of)],
        ).fetchall()
        return [self._row_to_observation(row) for row in rows]

    def count_definitions(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM operating_metric_definitions").fetchone()[0])

    def count_observations(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM operating_metric_observations").fetchone()[0])

    def count_company_observations(self, company_id: str) -> int:
        return int(
            self.connection.execute(
                """SELECT count(*) FROM operating_metric_observations o
                   JOIN operating_metric_definitions d ON d.definition_id = o.definition_id
                   WHERE d.company_id = ?""",
                [company_id],
            ).fetchone()[0]
        )

    def _optional_definition(self, definition_id: str) -> OperatingMetricDefinition | None:
        row = self.connection.execute(
            f"SELECT {DEFINITION_COLUMNS} FROM operating_metric_definitions WHERE definition_id = ?",
            [definition_id],
        ).fetchone()
        return self._row_to_definition(row) if row else None

    def _require_observation(self, observation_id: str) -> OperatingMetricObservation:
        observation = self.get_observation(observation_id)
        if observation is None:
            raise LookupError(f"No operating metric observation exists for observation_id {observation_id}.")
        return observation

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
                raise ValueError("Operating intelligence evidence must belong to the selected company.")
            if document.known_at > known_at:
                raise ValueError("Operating intelligence known_at cannot precede its source evidence.")
            spans.append(span)
        return spans

    def _link(self, claim_type: str, claim_id: str, span_id: str) -> None:
        self.evidence.link_claim(
            EvidenceClaimLinkCreate(
                claim_type=claim_type,
                claim_id=claim_id,
                span_id=span_id,
            )
        )

    @staticmethod
    def _definition_id(command: OperatingMetricDefinitionCreate, version: int) -> str:
        payload = {
            **command.model_dump(mode="json", exclude={"evidence_span_ids"}),
            "version": version,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _same_definition(
        existing: OperatingMetricDefinition,
        command: OperatingMetricDefinitionCreate,
    ) -> bool:
        return (
            existing.company_id == command.company_id
            and existing.category == command.category
            and existing.definition_key == command.definition_key
            and existing.label == command.label
            and existing.measure == command.measure
            and existing.unit == command.unit
            and existing.value_type == command.value_type
            and existing.reporting_basis == command.reporting_basis
            and existing.valid_from == command.valid_from
            and existing.valid_to == command.valid_to
            and existing.description == command.description
        )

    @staticmethod
    def _observation_id(command: OperatingMetricObservationCreate) -> str:
        payload = command.model_dump(mode="json", exclude={"evidence_span_ids"})
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _row_to_definition(row: tuple) -> OperatingMetricDefinition:
        return OperatingMetricDefinition(
            definition_id=row[0],
            company_id=row[1],
            category=row[2],
            definition_key=row[3],
            label=row[4],
            measure=row[5],
            unit=row[6],
            value_type=row[7],
            reporting_basis=row[8],
            version=row[9],
            valid_from=row[10],
            valid_to=row[11],
            supersedes_definition_id=row[12],
            description=row[13],
            known_at=OperationsRepository._aware_utc(row[14]),
            extraction_method=row[15],
            model_version=row[16],
            created_at=OperationsRepository._aware_utc(row[17]),
        )

    @staticmethod
    def _row_to_observation(row: tuple) -> OperatingMetricObservation:
        return OperatingMetricObservation(
            observation_id=row[0],
            definition_id=row[1],
            period_start=row[2],
            period_end=row[3],
            fiscal_year=row[4],
            fiscal_period=row[5],
            value=row[6],
            unit=row[7],
            known_at=OperationsRepository._aware_utc(row[8]),
            extraction_method=row[9],
            created_at=OperationsRepository._aware_utc(row[10]),
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
