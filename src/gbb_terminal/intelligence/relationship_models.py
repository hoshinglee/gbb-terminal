from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .evidence_models import EvidenceClaimLink, EvidenceDocument, EvidenceSpan
from .models import CompanyIdentity


RELATIONSHIP_MODEL_VERSION = "1.0.0"


class RelationshipType(StrEnum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    MANUFACTURER_FOUNDRY = "manufacturer_foundry"
    DISTRIBUTOR = "distributor"
    STRATEGIC_PARTNER = "strategic_partner"
    COMPETITOR = "competitor"
    CUSTOMER_CONCENTRATION = "customer_concentration"
    SUPPLIER_CONCENTRATION = "supplier_concentration"


class RelationshipDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    MARKET = "market"


class RelationshipConfidence(StrEnum):
    DISCLOSED = "disclosed"
    STRONGLY_INFERRED = "strongly_inferred"
    INFERRED = "inferred"


class RelationshipObservationKind(StrEnum):
    EXTRACTED = "extracted"
    HUMAN_OVERRIDE = "human_override"


class RelationshipCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_company_id: str = Field(min_length=1, max_length=120)
    target_company_id: str | None = Field(default=None, min_length=1, max_length=120)
    raw_counterparty_name: str = Field(min_length=1, max_length=300)
    relationship_type: RelationshipType
    direction: RelationshipDirection
    exposure_value: float | None = None
    exposure_unit: str | None = Field(default=None, min_length=1, max_length=120)
    valid_from: date | None = None
    valid_to: date | None = None
    known_at: datetime
    extraction_method: str = Field(min_length=1, max_length=160)
    confidence: RelationshipConfidence
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)
    observation_kind: RelationshipObservationKind = RelationshipObservationKind.EXTRACTED
    correction_note: str | None = Field(default=None, max_length=2000)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Relationship known_at must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_relationship(self) -> "RelationshipCandidate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Relationship valid_to cannot precede valid_from.")
        if (self.exposure_value is None) != (self.exposure_unit is None):
            raise ValueError("Relationship exposure_value and exposure_unit must be supplied together.")
        if self.observation_kind == RelationshipObservationKind.HUMAN_OVERRIDE and not self.correction_note:
            raise ValueError("A human relationship override requires a correction note.")
        return self


class RelationshipOverrideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_company_id: str | None = Field(default=None, min_length=1, max_length=120)
    exposure_value: float | None = None
    exposure_unit: str | None = Field(default=None, min_length=1, max_length=120)
    valid_from: date | None = None
    valid_to: date | None = None
    known_at: datetime
    confidence: RelationshipConfidence
    evidence_span_ids: list[str] = Field(min_length=1, max_length=50)
    correction_note: str = Field(min_length=1, max_length=2000)

    @field_validator("known_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Relationship override known_at must include a timezone.")
        return value

    @field_validator("evidence_span_ids")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_override(self) -> "RelationshipOverrideCreate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Relationship valid_to cannot precede valid_from.")
        if (self.exposure_value is None) != (self.exposure_unit is None):
            raise ValueError("Relationship exposure_value and exposure_unit must be supplied together.")
        return self


class RelationshipEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    source_company_id: str
    normalized_counterparty_name: str
    raw_counterparty_name: str
    relationship_type: RelationshipType
    direction: RelationshipDirection
    model_version: str = RELATIONSHIP_MODEL_VERSION
    created_at: datetime


class RelationshipObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    relationship_id: str
    target_company_id: str | None = None
    exposure_value: float | None = None
    exposure_unit: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    known_at: datetime
    extraction_method: str
    confidence: RelationshipConfidence
    observation_kind: RelationshipObservationKind
    supersedes_observation_id: str | None = None
    correction_note: str | None = None
    created_at: datetime


class RelationshipEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: EvidenceClaimLink
    document: EvidenceDocument
    span: EvidenceSpan


class CompanyRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge: RelationshipEdge
    observation: RelationshipObservation
    source_company: CompanyIdentity
    target_company: CompanyIdentity | None = None
    perspective_direction: RelationshipDirection
    evidence: list[RelationshipEvidence]


class RelationshipNetwork(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyIdentity
    as_of: datetime
    relationships: list[CompanyRelationship]
    matching_relationship_count: int
    warnings: list[str] = Field(default_factory=list)


class RelationshipHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: CompanyIdentity
    as_of: datetime
    edge: RelationshipEdge
    observations: list[RelationshipObservation]
    evidence: dict[str, list[RelationshipEvidence]]


class RelationshipNetworkQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directions: list[RelationshipDirection] = Field(default_factory=list, max_length=4)
    relationship_types: list[RelationshipType] = Field(default_factory=list, max_length=20)
    confidences: list[RelationshipConfidence] = Field(default_factory=list, max_length=3)
    as_of: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Relationship as_of must include a timezone.")
        return value
