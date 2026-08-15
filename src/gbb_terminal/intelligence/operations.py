from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .evidence_repository import EvidenceRepository
from .operations_models import (
    OperatingDefinitionTransition,
    OperatingIntelligence,
    OperatingIntelligenceQuery,
    OperatingMetricCategory,
    OperatingMetricDefinition,
    OperatingMetricEvidence,
    OperatingMetricPoint,
    OperatingMetricSeries,
)
from .operations_repository import OperationsRepository
from .service import CompanyIdentityService


class OperationsIntelligenceService:
    def __init__(
        self,
        repository: OperationsRepository,
        evidence: EvidenceRepository,
        identities: CompanyIdentityService,
    ) -> None:
        self.repository = repository
        self.evidence = evidence
        self.identities = identities

    def history(self, ticker: str, query: OperatingIntelligenceQuery) -> OperatingIntelligence:
        company = self.identities.resolve_ticker(ticker)
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {ticker.upper()}.")
        as_of = (query.as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        effective_query = query.model_copy(update={"as_of": as_of})
        definitions = self.repository.list_definitions(company.company_id, effective_query)
        observations = {
            definition.definition_id: self._latest_period_observations(
                self.repository.list_observations(definition.definition_id, as_of)
            )
            for definition in definitions
        }
        totals: dict[tuple, float] = defaultdict(float)
        for definition in definitions:
            if definition.category not in {OperatingMetricCategory.SEGMENT, OperatingMetricCategory.GEOGRAPHY}:
                continue
            for observation in observations[definition.definition_id]:
                totals[self._mix_key(definition, observation.period_end)] += observation.value

        series = []
        for definition in definitions:
            previous_value = None
            points = []
            for observation in observations[definition.definition_id]:
                total = totals.get(self._mix_key(definition, observation.period_end))
                mix_percent = (
                    round(observation.value / total * 100, 6)
                    if definition.category in {OperatingMetricCategory.SEGMENT, OperatingMetricCategory.GEOGRAPHY}
                    and total not in {None, 0}
                    else None
                )
                growth_percent = (
                    round((observation.value / previous_value - 1) * 100, 6)
                    if previous_value not in {None, 0}
                    else None
                )
                points.append(
                    OperatingMetricPoint(
                        observation=observation,
                        mix_percent=mix_percent,
                        growth_percent=growth_percent,
                        evidence=self._evidence(
                            company.company_id,
                            "operating_observation",
                            observation.observation_id,
                            as_of,
                        ),
                    )
                )
                previous_value = observation.value
            series.append(
                OperatingMetricSeries(
                    definition=definition,
                    definition_evidence=self._evidence(
                        company.company_id,
                        "operating_definition",
                        definition.definition_id,
                        as_of,
                    ),
                    points=points,
                )
            )

        by_id = {definition.definition_id: definition for definition in definitions}
        transitions = [
            self._transition(by_id[definition.supersedes_definition_id], definition)
            for definition in definitions
            if definition.supersedes_definition_id in by_id
        ]
        warnings = []
        requested_categories = set(query.categories or list(OperatingMetricCategory))
        available_categories = {definition.category for definition in definitions}
        for category in sorted(requested_categories - available_categories, key=lambda item: item.value):
            warnings.append(
                f"No source-backed {category.value} observations are available inside this as-of boundary."
            )
        if transitions:
            warnings.append(
                "Reported definitions changed over time; growth and mix are calculated only inside compatible definition versions and reporting bases."
            )
        warnings.append(
            "Company-specific KPI and geographic coverage follows issuer disclosures and may be incomplete or non-standardized."
        )
        return OperatingIntelligence(
            company=company,
            as_of=as_of,
            series=series,
            transitions=transitions,
            warnings=warnings,
        )

    def _evidence(
        self,
        company_id: str,
        claim_type: str,
        claim_id: str,
        as_of: datetime,
    ) -> list[OperatingMetricEvidence]:
        result = []
        for claim_span in self.evidence.list_claim_spans(company_id, claim_type, claim_id, as_of):
            document = self.evidence.get_document(claim_span.span.document_id)
            if document is not None:
                result.append(
                    OperatingMetricEvidence(
                        link=claim_span.link,
                        document=document,
                        span=claim_span.span,
                    )
                )
        return result

    @staticmethod
    def _latest_period_observations(observations):
        latest = {}
        for observation in observations:
            latest[observation.period_end] = observation
        return [latest[period_end] for period_end in sorted(latest)]

    @staticmethod
    def _mix_key(definition: OperatingMetricDefinition, period_end) -> tuple:
        return (
            definition.category,
            definition.reporting_basis,
            definition.measure,
            definition.unit,
            period_end,
        )

    @staticmethod
    def _transition(
        prior: OperatingMetricDefinition,
        current: OperatingMetricDefinition,
    ) -> OperatingDefinitionTransition:
        return OperatingDefinitionTransition(
            prior_definition_id=prior.definition_id,
            next_definition_id=current.definition_id,
            definition_key=current.definition_key,
            prior_label=prior.label,
            next_label=current.label,
            prior_reporting_basis=prior.reporting_basis,
            next_reporting_basis=current.reporting_basis,
            known_at=current.known_at,
        )
