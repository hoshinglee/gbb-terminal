from __future__ import annotations

import re
from datetime import datetime, timezone

from .evidence_models import EvidenceDocument, EvidenceSpan
from .evidence_repository import EvidenceRepository
from .relationship_models import (
    CompanyRelationship,
    RelationshipCandidate,
    RelationshipConfidence,
    RelationshipDirection,
    RelationshipEvidence,
    RelationshipHistory,
    RelationshipNetwork,
    RelationshipNetworkQuery,
    RelationshipObservationKind,
    RelationshipOverrideCreate,
    RelationshipType,
)
from .relationship_repository import RelationshipRepository
from .service import CompanyIdentityService


RELATIONSHIP_EXTRACTION_METHOD = "deterministic_relationship_rules_v3"


class RelationshipExtractor:
    concentration_pattern = re.compile(
        r"\b(?P<name>Customer\s+[A-Z0-9]+|[A-Z][A-Za-z0-9&.'’\- ]{1,100}?)\s+"
        r"(?:represented|accounted\s+for|comprised)\s+(?:approximately\s+|about\s+|more\s+than\s+)?"
        r"(?P<exposure>\d+(?:\.\d+)?)%\s+of\s+(?:our\s+)?(?:total\s+|net\s+)?revenue\b",
    )
    supplier_concentration_pattern = re.compile(
        r"\b(?P<name>Supplier\s+[A-Z0-9]+|[A-Z][A-Za-z0-9&.'’\- ]{1,100}?)\s+"
        r"(?:represented|accounted\s+for|comprised)\s+(?:approximately\s+|about\s+|more\s+than\s+)?"
        r"(?P<exposure>\d+(?:\.\d+)?)%\s+of\s+(?:our\s+)?(?:total\s+)?(?:purchases|supply)\b",
    )
    serves_pattern = re.compile(
        r"\b(?P<name>[A-Z][A-Za-z0-9&.'’\- ]{1,100}?)\s+(?:is|serves|served)\s+"
        r"(?:as\s+)?(?:our|a)\s+(?P<role>supplier|customer|foundry|manufacturer|distributor|"
        r"strategic\s+partner|competitor)\b",
    )
    dependency_pattern = re.compile(
        r"\b(?:We|The\s+Company)\s+(?:rely|relies|depend|depends)\s+(?:primarily\s+)?(?:on|upon)\s+"
        r"(?P<name>[A-Z][A-Za-z0-9&.'’\- ]{1,100}?)\s+(?:as|for)\s+(?:our\s+)?"
        r"(?P<role>supplier|foundry|manufacturer|distributor)\b",
    )
    competitor_pattern = re.compile(
        r"\b(?:We|The\s+Company)\s+compete(?:s)?\s+with\s+"
        r"(?P<name>[A-Z][A-Za-z0-9&.'’\- ]{1,100}?)(?:[.,;]|\s+in\s+the\s+market)",
    )
    named_role_list_pattern = re.compile(
        r"\b(?P<role>foundries|suppliers|contract\s+manufacturers|manufacturers|distributors)"
        r"\s*,?\s+(?:including|such\s+as)\s+(?P<names>.{2,500}?)"
        r"(?=(?:,\s*)?\b(?:to|for)\b|;|\.(?:\s|$)|$)",
        re.IGNORECASE,
    )
    purchase_from_pattern = re.compile(
        r"\b(?:We|The\s+Company)\s+(?:purchase|source|procure)\s+.{0,100}?\s+from\s+(?P<names>.{2,500}?)"
        r"(?=;|\.(?:\s|$)|$)",
        re.IGNORECASE,
    )
    competition_list_pattern = re.compile(
        r"\b(?:such\s+as|include(?:s|d)?)\s+(?P<names>.{2,500}?)(?=;|\.(?:\s|$)|$)",
        re.IGNORECASE,
    )
    alias_pattern = re.compile(
        r",\s+or\s+[A-Z][A-Za-z0-9&.'’\-]{1,40}(?=\s*,|\s+and\b|$)",
    )
    legal_suffix_comma_pattern = re.compile(
        r",\s+(?=(?:Inc\.?|Incorporated|Corp\.?|Corporation|Co\.?|Ltd\.?|Limited|LLC|plc)\b)",
        re.IGNORECASE,
    )
    legal_entity_pattern = re.compile(
        r"\b(?:Inc\.?|Incorporated|Corp\.?|Corporation|Company|Co\.?|Ltd\.?|Limited|LLC|plc)\.?$",
        re.IGNORECASE,
    )

    def __init__(self, repository: RelationshipRepository) -> None:
        self.repository = repository

    def candidates(
        self,
        company_id: str,
        document: EvidenceDocument,
        span: EvidenceSpan,
    ) -> list[RelationshipCandidate]:
        if document.company_id != company_id or span.document_id != document.document_id:
            raise ValueError("Relationship extraction evidence does not belong to the selected company.")
        candidates: list[RelationshipCandidate] = []
        sentences = re.split(r"(?<=[.!?])\s+", span.exact_text)
        for sentence in sentences:
            for match in self.concentration_pattern.finditer(sentence):
                candidates.append(
                    self._candidate(
                        company_id,
                        document,
                        span,
                        match.group("name"),
                        RelationshipType.CUSTOMER_CONCENTRATION,
                        RelationshipDirection.DOWNSTREAM,
                        float(match.group("exposure")),
                        "% of revenue",
                    )
                )
            for match in self.supplier_concentration_pattern.finditer(sentence):
                candidates.append(
                    self._candidate(
                        company_id,
                        document,
                        span,
                        match.group("name"),
                        RelationshipType.SUPPLIER_CONCENTRATION,
                        RelationshipDirection.UPSTREAM,
                        float(match.group("exposure")),
                        "% of purchases",
                    )
                )
            for pattern in (self.serves_pattern, self.dependency_pattern):
                for match in pattern.finditer(sentence):
                    relationship_type, direction = self._role(match.group("role"))
                    candidates.append(
                        self._candidate(
                            company_id,
                            document,
                            span,
                            match.group("name"),
                            relationship_type,
                            direction,
                        )
                    )
            for match in self.competitor_pattern.finditer(sentence):
                candidates.append(
                    self._candidate(
                        company_id,
                        document,
                        span,
                        match.group("name"),
                        RelationshipType.COMPETITOR,
                        RelationshipDirection.MARKET,
                    )
                )
            for match in self.named_role_list_pattern.finditer(sentence):
                relationship_type, direction = self._role(match.group("role"))
                candidates.extend(
                    self._list_candidates(
                        company_id,
                        document,
                        span,
                        match.group("names"),
                        relationship_type,
                        direction,
                    )
                )
            for match in self.purchase_from_pattern.finditer(sentence):
                candidates.extend(
                    self._list_candidates(
                        company_id,
                        document,
                        span,
                        match.group("names"),
                        RelationshipType.SUPPLIER,
                        RelationshipDirection.UPSTREAM,
                    )
                )
            if span.section and "compet" in span.section.casefold():
                for match in self.competition_list_pattern.finditer(sentence):
                    candidates.extend(
                        self._list_candidates(
                            company_id,
                            document,
                            span,
                            match.group("names"),
                            RelationshipType.COMPETITOR,
                            RelationshipDirection.MARKET,
                        )
                    )
        unique: dict[tuple, RelationshipCandidate] = {}
        for candidate in candidates:
            key = (
                candidate.raw_counterparty_name.casefold(),
                candidate.relationship_type,
                candidate.direction,
                candidate.exposure_value,
                candidate.exposure_unit,
            )
            unique[key] = candidate
        return list(unique.values())

    def _list_candidates(
        self,
        company_id: str,
        document: EvidenceDocument,
        span: EvidenceSpan,
        names: str,
        relationship_type: RelationshipType,
        direction: RelationshipDirection,
    ) -> list[RelationshipCandidate]:
        normalized = self.alias_pattern.sub("", names)
        normalized = re.split(r",\s+or\s+(?:companies|businesses|other\s+organizations)\b", normalized, maxsplit=1)[0]
        normalized = self.legal_suffix_comma_pattern.sub(" ", normalized)
        candidates = []
        for raw_name in re.split(r"\s*,\s*|\s+and\s+", normalized):
            name = raw_name.strip(" •,.;:-")
            name = re.sub(r"^(?:and|or)\s+", "", name, flags=re.IGNORECASE)
            if not self._looks_like_counterparty(name):
                continue
            candidates.append(
                self._candidate(
                    company_id,
                    document,
                    span,
                    name,
                    relationship_type,
                    direction,
                )
            )
        return candidates

    def _looks_like_counterparty(self, name: str) -> bool:
        if not 2 <= len(name) <= 160 or len(name.split()) > 14:
            return False
        normalized = name.casefold()
        if normalized.startswith(("companies", "businesses", "other ", "certain ", "third-party")):
            return False
        return self.repository.resolve_company_name(name) is not None or bool(self.legal_entity_pattern.search(name))

    def _candidate(
        self,
        company_id: str,
        document: EvidenceDocument,
        span: EvidenceSpan,
        raw_name: str,
        relationship_type: RelationshipType,
        direction: RelationshipDirection,
        exposure_value: float | None = None,
        exposure_unit: str | None = None,
    ) -> RelationshipCandidate:
        name = raw_name.strip(" ,.;:-")
        return RelationshipCandidate(
            source_company_id=company_id,
            target_company_id=self.repository.resolve_company_name(name),
            raw_counterparty_name=name,
            relationship_type=relationship_type,
            direction=direction,
            exposure_value=exposure_value,
            exposure_unit=exposure_unit,
            known_at=document.known_at,
            extraction_method=RELATIONSHIP_EXTRACTION_METHOD,
            confidence=RelationshipConfidence.DISCLOSED,
            evidence_span_ids=[span.span_id],
        )

    @staticmethod
    def _role(role: str) -> tuple[RelationshipType, RelationshipDirection]:
        normalized = " ".join(role.casefold().split())
        if normalized in {"supplier", "suppliers"}:
            return RelationshipType.SUPPLIER, RelationshipDirection.UPSTREAM
        if normalized in {
            "foundry",
            "foundries",
            "manufacturer",
            "manufacturers",
            "contract manufacturer",
            "contract manufacturers",
        }:
            return RelationshipType.MANUFACTURER_FOUNDRY, RelationshipDirection.UPSTREAM
        if normalized in {"customer", "customers"}:
            return RelationshipType.CUSTOMER, RelationshipDirection.DOWNSTREAM
        if normalized in {"distributor", "distributors"}:
            return RelationshipType.DISTRIBUTOR, RelationshipDirection.DOWNSTREAM
        if normalized == "strategic partner":
            return RelationshipType.STRATEGIC_PARTNER, RelationshipDirection.BIDIRECTIONAL
        return RelationshipType.COMPETITOR, RelationshipDirection.MARKET


class RelationshipService:
    def __init__(
        self,
        repository: RelationshipRepository,
        evidence: EvidenceRepository,
        identities: CompanyIdentityService,
    ) -> None:
        self.repository = repository
        self.evidence = evidence
        self.identities = identities
        self.extractor = RelationshipExtractor(repository)

    def extract_span(self, ticker: str, span_id: str) -> list[CompanyRelationship]:
        company = self._company(ticker)
        span = self.evidence.get_span(span_id)
        document = self.evidence.get_document(span.document_id) if span else None
        if span is None or document is None or document.company_id != company.company_id:
            raise LookupError(f"No extractable evidence span {span_id} exists for {ticker.upper()}.")
        records = []
        for candidate in self.extractor.candidates(company.company_id, document, span):
            edge, observation = self.repository.save_candidate(candidate)
            records.append(self._record(company, edge, observation, observation.known_at))
        return records

    def save_candidate(self, candidate: RelationshipCandidate) -> tuple:
        return self.repository.save_candidate(candidate)

    def network(self, ticker: str, query: RelationshipNetworkQuery) -> RelationshipNetwork:
        company = self._company(ticker)
        as_of = (query.as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        records: list[CompanyRelationship] = []
        missing_evidence = 0
        for edge, observation in self.repository.list_current(company.company_id, as_of):
            direction = self._perspective_direction(company.company_id, edge.source_company_id, edge.direction)
            if query.directions and direction not in query.directions:
                continue
            if query.relationship_types and edge.relationship_type not in query.relationship_types:
                continue
            if query.confidences and observation.confidence not in query.confidences:
                continue
            record = self._record(company, edge, observation, as_of)
            if not record.evidence:
                missing_evidence += 1
                continue
            records.append(record)
        matching_count = len(records)
        warnings = [
            "Public company disclosures are incomplete; absence of a relationship is not evidence that none exists."
        ]
        if matching_count > query.limit:
            warnings.append(
                f"The response contains the first {query.limit} of {matching_count} matching relationships."
            )
        if missing_evidence:
            warnings.append(
                f"{missing_evidence} relationship record(s) were withheld because inspectable source evidence was unavailable."
            )
        if not records:
            warnings.append("No source-backed relationships are available inside this as-of boundary and filter set.")
        return RelationshipNetwork(
            company=company,
            as_of=as_of,
            relationships=records[: query.limit],
            matching_relationship_count=matching_count,
            warnings=warnings,
        )

    def history(
        self,
        ticker: str,
        relationship_id: str,
        as_of: datetime | None = None,
    ) -> RelationshipHistory:
        company = self._company(ticker)
        effective_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        edge = self.repository.get_edge(relationship_id)
        observations = self.repository.list_observations(relationship_id, effective_as_of)
        involved = edge.source_company_id == company.company_id or any(
            observation.target_company_id == company.company_id for observation in observations
        )
        if not involved:
            raise LookupError(f"Relationship {relationship_id} is not associated with {ticker.upper()}.")
        evidence = {
            observation.observation_id: self._evidence(
                edge.source_company_id,
                observation.observation_id,
                effective_as_of,
            )
            for observation in observations
        }
        return RelationshipHistory(
            company=company,
            as_of=effective_as_of,
            edge=edge,
            observations=observations,
            evidence=evidence,
        )

    def override(
        self,
        ticker: str,
        relationship_id: str,
        command: RelationshipOverrideCreate,
    ) -> CompanyRelationship:
        company = self._company(ticker)
        edge = self.repository.get_edge(relationship_id)
        prior = self.repository.latest_observation(relationship_id, command.known_at)
        if prior is None:
            raise LookupError(f"Relationship {relationship_id} has no observation to correct.")
        if edge.source_company_id != company.company_id and prior.target_company_id != company.company_id:
            raise LookupError(f"Relationship {relationship_id} is not associated with {ticker.upper()}.")
        candidate = RelationshipCandidate(
            source_company_id=edge.source_company_id,
            target_company_id=command.target_company_id,
            raw_counterparty_name=edge.raw_counterparty_name,
            relationship_type=edge.relationship_type,
            direction=edge.direction,
            exposure_value=command.exposure_value,
            exposure_unit=command.exposure_unit,
            valid_from=command.valid_from,
            valid_to=command.valid_to,
            known_at=command.known_at,
            extraction_method="human_override",
            confidence=command.confidence,
            evidence_span_ids=command.evidence_span_ids,
            observation_kind=RelationshipObservationKind.HUMAN_OVERRIDE,
            correction_note=command.correction_note,
        )
        saved_edge, observation = self.repository.save_candidate(candidate)
        return self._record(company, saved_edge, observation, observation.known_at)

    def _record(self, center, edge, observation, as_of: datetime) -> CompanyRelationship:
        source_company = self.identities.repository.get_company(edge.source_company_id)
        target_company = (
            self.identities.repository.get_company(observation.target_company_id)
            if observation.target_company_id
            else None
        )
        return CompanyRelationship(
            edge=edge,
            observation=observation,
            source_company=source_company,
            target_company=target_company,
            perspective_direction=self._perspective_direction(
                center.company_id,
                edge.source_company_id,
                edge.direction,
            ),
            evidence=self._evidence(edge.source_company_id, observation.observation_id, as_of),
        )

    def _evidence(
        self,
        source_company_id: str,
        observation_id: str,
        as_of: datetime,
    ) -> list[RelationshipEvidence]:
        result = []
        for claim_span in self.evidence.list_claim_spans(
            source_company_id,
            "relationship",
            observation_id,
            as_of,
        ):
            document = self.evidence.get_document(claim_span.span.document_id)
            if document is not None:
                result.append(
                    RelationshipEvidence(
                        link=claim_span.link,
                        document=document,
                        span=claim_span.span,
                    )
                )
        return result

    def _company(self, ticker: str):
        company = self.identities.resolve_ticker(ticker)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {ticker.upper()}.")
        return company

    @staticmethod
    def _perspective_direction(
        center_company_id: str,
        source_company_id: str,
        direction: RelationshipDirection,
    ) -> RelationshipDirection:
        if center_company_id == source_company_id:
            return direction
        if direction == RelationshipDirection.UPSTREAM:
            return RelationshipDirection.DOWNSTREAM
        if direction == RelationshipDirection.DOWNSTREAM:
            return RelationshipDirection.UPSTREAM
        return direction
