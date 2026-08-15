from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha256

import duckdb

from .evidence_models import EvidenceClaimLinkCreate
from .evidence_repository import EvidenceRepository
from .relationship_models import (
    RELATIONSHIP_MODEL_VERSION,
    RelationshipCandidate,
    RelationshipEdge,
    RelationshipObservation,
)


EDGE_COLUMNS = """relationship_id, source_company_id, normalized_counterparty_name, raw_counterparty_name,
    relationship_type, direction, model_version, created_at"""

OBSERVATION_COLUMNS = """observation_id, relationship_id, target_company_id, exposure_value, exposure_unit,
    valid_from, valid_to, known_at, extraction_method, confidence, observation_kind,
    supersedes_observation_id, correction_note, created_at"""

LEGAL_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "plc",
}


def normalize_counterparty_name(value: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip().split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


class RelationshipRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection, evidence: EvidenceRepository) -> None:
        self.connection = connection
        self.evidence = evidence

    def save_candidate(self, candidate: RelationshipCandidate) -> tuple[RelationshipEdge, RelationshipObservation]:
        normalized_name = normalize_counterparty_name(candidate.raw_counterparty_name)
        if not normalized_name:
            raise ValueError("A relationship counterparty must contain a searchable name.")
        self._require_company(candidate.source_company_id)
        if candidate.target_company_id:
            self._require_company(candidate.target_company_id)
            if candidate.target_company_id == candidate.source_company_id:
                raise ValueError("A company relationship cannot target itself.")
        spans = self._require_source_evidence(
            candidate.source_company_id,
            candidate.evidence_span_ids,
            candidate.known_at,
        )
        relationship_id = sha256(
            "\0".join(
                (
                    candidate.source_company_id,
                    normalized_name,
                    candidate.relationship_type.value,
                    candidate.direction.value,
                )
            ).encode()
        ).hexdigest()
        observation_id = self._observation_id(relationship_id, candidate)
        now = self._utc_now()
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                """INSERT INTO business_relationships
                   (relationship_id, source_company_id, normalized_counterparty_name, raw_counterparty_name,
                    relationship_type, direction, model_version, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (relationship_id) DO NOTHING""",
                [
                    relationship_id,
                    candidate.source_company_id,
                    normalized_name,
                    candidate.raw_counterparty_name,
                    candidate.relationship_type.value,
                    candidate.direction.value,
                    RELATIONSHIP_MODEL_VERSION,
                    now,
                ],
            )
            existing = self.get_observation(observation_id)
            if existing is None:
                latest = self.latest_observation(relationship_id, candidate.known_at)
                supersedes_observation_id = latest.observation_id if latest else None
                self.connection.execute(
                    """INSERT INTO relationship_observations
                       (observation_id, relationship_id, target_company_id, exposure_value, exposure_unit,
                        valid_from, valid_to, known_at, extraction_method, confidence, observation_kind,
                        supersedes_observation_id, correction_note, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        observation_id,
                        relationship_id,
                        candidate.target_company_id,
                        candidate.exposure_value,
                        candidate.exposure_unit,
                        candidate.valid_from,
                        candidate.valid_to,
                        self._naive_utc(candidate.known_at),
                        candidate.extraction_method,
                        candidate.confidence.value,
                        candidate.observation_kind.value,
                        supersedes_observation_id,
                        candidate.correction_note,
                        now,
                    ],
                )
            for span in spans:
                self.evidence.link_claim(
                    EvidenceClaimLinkCreate(
                        claim_type="relationship",
                        claim_id=observation_id,
                        span_id=span.span_id,
                    )
                )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_edge(relationship_id), self._require_observation(observation_id)

    def add_evidence(self, observation_id: str, span_id: str) -> None:
        observation = self._require_observation(observation_id)
        edge = self.get_edge(observation.relationship_id)
        self._require_source_evidence(edge.source_company_id, [span_id], observation.known_at)
        self.evidence.link_claim(
            EvidenceClaimLinkCreate(
                claim_type="relationship",
                claim_id=observation_id,
                span_id=span_id,
            )
        )

    def get_edge(self, relationship_id: str) -> RelationshipEdge:
        row = self.connection.execute(
            f"SELECT {EDGE_COLUMNS} FROM business_relationships WHERE relationship_id = ?",
            [relationship_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"No business relationship exists for relationship_id {relationship_id}.")
        return self._row_to_edge(row)

    def get_observation(self, observation_id: str) -> RelationshipObservation | None:
        row = self.connection.execute(
            f"SELECT {OBSERVATION_COLUMNS} FROM relationship_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def latest_observation(
        self,
        relationship_id: str,
        as_of: datetime | None = None,
    ) -> RelationshipObservation | None:
        condition = "relationship_id = ?"
        parameters: list[object] = [relationship_id]
        if as_of is not None:
            condition += " AND known_at <= ?"
            parameters.append(self._naive_utc(as_of))
        row = self.connection.execute(
            f"""SELECT {OBSERVATION_COLUMNS} FROM relationship_observations
                WHERE {condition} ORDER BY known_at DESC, created_at DESC LIMIT 1""",
            parameters,
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def list_observations(
        self,
        relationship_id: str,
        as_of: datetime | None = None,
    ) -> list[RelationshipObservation]:
        self.get_edge(relationship_id)
        condition = "relationship_id = ?"
        parameters: list[object] = [relationship_id]
        if as_of is not None:
            condition += " AND known_at <= ?"
            parameters.append(self._naive_utc(as_of))
        rows = self.connection.execute(
            f"""SELECT {OBSERVATION_COLUMNS} FROM relationship_observations
                WHERE {condition} ORDER BY known_at, created_at""",
            parameters,
        ).fetchall()
        return [self._row_to_observation(row) for row in rows]

    def list_current(
        self,
        company_id: str,
        as_of: datetime,
    ) -> list[tuple[RelationshipEdge, RelationshipObservation]]:
        self._require_company(company_id)
        edge_column_count = len(EDGE_COLUMNS.split(","))
        qualified_edges = ", ".join(f"r.{column.strip()}" for column in EDGE_COLUMNS.split(","))
        qualified_observations = ", ".join(f"ranked.{column.strip()}" for column in OBSERVATION_COLUMNS.split(","))
        rows = self.connection.execute(
            f"""WITH ranked AS (
                    SELECT o.*, row_number() OVER (
                        PARTITION BY o.relationship_id ORDER BY o.known_at DESC, o.created_at DESC
                    ) AS observation_rank
                    FROM relationship_observations o
                    WHERE o.known_at <= ?
                )
                SELECT {qualified_edges}, {qualified_observations}
                FROM ranked
                JOIN business_relationships r ON r.relationship_id = ranked.relationship_id
                WHERE ranked.observation_rank = 1
                  AND (ranked.valid_from IS NULL OR ranked.valid_from <= ?)
                  AND (ranked.valid_to IS NULL OR ranked.valid_to >= ?)
                  AND (r.source_company_id = ? OR ranked.target_company_id = ?)
                ORDER BY r.relationship_type, r.raw_counterparty_name""",
            [
                self._naive_utc(as_of),
                as_of.date(),
                as_of.date(),
                company_id,
                company_id,
            ],
        ).fetchall()
        return [
            (
                self._row_to_edge(row[:edge_column_count]),
                self._row_to_observation(row[edge_column_count:]),
            )
            for row in rows
        ]

    def resolve_company_name(self, raw_name: str) -> str | None:
        normalized_name = normalize_counterparty_name(raw_name)
        if not normalized_name:
            return None
        rows = self.connection.execute(
            "SELECT company_id, legal_name FROM companies ORDER BY company_id"
        ).fetchall()
        legal_matches = [company_id for company_id, legal_name in rows if normalize_counterparty_name(legal_name) == normalized_name]
        if len(legal_matches) == 1:
            return legal_matches[0]
        ticker_rows = self.connection.execute(
            """SELECT DISTINCT company_id, ticker FROM company_security_mappings
               WHERE status = 'active' ORDER BY company_id"""
        ).fetchall()
        ticker_matches = [company_id for company_id, ticker in ticker_rows if ticker.casefold() == raw_name.strip().casefold()]
        return ticker_matches[0] if len(ticker_matches) == 1 else None

    def count_edges(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM business_relationships").fetchone()[0])

    def count_observations(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM relationship_observations").fetchone()[0])

    def _require_source_evidence(self, company_id: str, span_ids: list[str], known_at: datetime):
        spans = []
        for span_id in span_ids:
            span = self.evidence.get_span(span_id)
            document = self.evidence.get_document(span.document_id) if span else None
            if span is None or document is None:
                raise LookupError(f"No evidence span exists for span_id {span_id}.")
            if document.company_id != company_id:
                raise ValueError("Relationship evidence must belong to the disclosing source company.")
            if document.known_at > known_at.astimezone(timezone.utc):
                raise ValueError("Relationship known_at cannot precede its source evidence.")
            spans.append(span)
        return spans

    def _require_company(self, company_id: str) -> None:
        if self.connection.execute("SELECT 1 FROM companies WHERE company_id = ?", [company_id]).fetchone() is None:
            raise LookupError(f"No canonical company exists for company_id {company_id}.")

    def _require_observation(self, observation_id: str) -> RelationshipObservation:
        observation = self.get_observation(observation_id)
        if observation is None:
            raise LookupError(f"No relationship observation exists for observation_id {observation_id}.")
        return observation

    @staticmethod
    def _observation_id(relationship_id: str, candidate: RelationshipCandidate) -> str:
        payload = {
            "relationship_id": relationship_id,
            "target_company_id": candidate.target_company_id,
            "exposure_value": candidate.exposure_value,
            "exposure_unit": candidate.exposure_unit,
            "valid_from": candidate.valid_from.isoformat() if candidate.valid_from else None,
            "valid_to": candidate.valid_to.isoformat() if candidate.valid_to else None,
            "known_at": candidate.known_at.astimezone(timezone.utc).isoformat(),
            "extraction_method": candidate.extraction_method,
            "confidence": candidate.confidence.value,
            "observation_kind": candidate.observation_kind.value,
            "correction_note": candidate.correction_note,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _row_to_edge(row: tuple) -> RelationshipEdge:
        return RelationshipEdge(
            relationship_id=row[0],
            source_company_id=row[1],
            normalized_counterparty_name=row[2],
            raw_counterparty_name=row[3],
            relationship_type=row[4],
            direction=row[5],
            model_version=row[6],
            created_at=RelationshipRepository._aware_utc(row[7]),
        )

    @staticmethod
    def _row_to_observation(row: tuple) -> RelationshipObservation:
        return RelationshipObservation(
            observation_id=row[0],
            relationship_id=row[1],
            target_company_id=row[2],
            exposure_value=row[3],
            exposure_unit=row[4],
            valid_from=row[5],
            valid_to=row[6],
            known_at=RelationshipRepository._aware_utc(row[7]),
            extraction_method=row[8],
            confidence=row[9],
            observation_kind=row[10],
            supersedes_observation_id=row[11],
            correction_note=row[12],
            created_at=RelationshipRepository._aware_utc(row[13]),
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
