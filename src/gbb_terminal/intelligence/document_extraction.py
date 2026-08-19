from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .document_parser import DOCUMENT_PARSER_VERSION, ParsedEvidenceDocument, ParsedTextBlock, ParsedXBRLFact
from .evidence_models import EvidenceDocument, EvidenceSpan, EvidenceSpanCreate
from .evidence_repository import EvidenceRepository
from .guidance_models import (
    GuidanceComparison,
    GuidanceStatementCreate,
    GuidanceStatementType,
    GuidanceValueKind,
)
from .guidance_repository import GuidanceRepository
from .operations_models import (
    OperatingMetricCategory,
    OperatingMetricDefinitionCreate,
    OperatingMetricObservationCreate,
    OperatingValueType,
)
from .operations_repository import OperationsRepository
from .relationships import RelationshipService


DOCUMENT_EXTRACTION_VERSION = "deterministic_public_document_v1"
OPERATIONS_EXTRACTION_VERSION = "deterministic_ixbrl_dimensions_v1"
GUIDANCE_EXTRACTION_VERSION = "deterministic_guidance_rules_v1"


@dataclass(frozen=True)
class DocumentExtractionResult:
    evidence_span_count: int
    relationship_count: int
    operating_observation_count: int
    guidance_statement_count: int
    warnings: list[str]


class OperationsDocumentExtractor:
    geography_axis_tokens = ("statementgeographicalaxis", "geographicalaxis", "geographyaxis", "countryaxis", "regionaxis")
    segment_axis_tokens = ("statementbusinesssegmentsaxis", "businesssegmentsaxis", "productorserviceaxis")
    kpi_tokens = (
        "subscriber",
        "user",
        "shipment",
        "location",
        "store",
        "customer",
        "employee",
        "seat",
        "capacity",
        "unitssold",
    )

    def __init__(self, repository: OperationsRepository) -> None:
        self.repository = repository

    def extract(
        self,
        company_id: str,
        document: EvidenceDocument,
        parsed: ParsedEvidenceDocument,
        fact_spans: dict[int, EvidenceSpan],
    ) -> tuple[int, list[str]]:
        before = self.repository.count_observations()
        warnings = []
        for index, fact in enumerate(parsed.facts):
            span = fact_spans.get(index)
            classification = self._classification(fact)
            if span is None or classification is None or fact.value is None or fact.context is None:
                continue
            if fact.context.period_end is None or not fact.unit:
                continue
            category, member, basis = classification
            measure = self._measure(fact.concept)
            definition_key = self._definition_key(category, member, measure)
            label = f"{self._label(member)} {self._label(measure)}".strip()
            value_type = self._value_type(fact.unit, fact.concept)
            latest = self.repository.latest_definition(company_id, category, definition_key)
            supersedes = None
            if latest and (
                latest.reporting_basis != basis
                or latest.unit != fact.unit
                or latest.measure != measure
                or latest.value_type != value_type
            ):
                supersedes = latest.definition_id
            try:
                definition = self.repository.save_definition(
                    OperatingMetricDefinitionCreate(
                        company_id=company_id,
                        category=category,
                        definition_key=definition_key,
                        label=label,
                        measure=measure,
                        unit=fact.unit,
                        value_type=value_type,
                        reporting_basis=basis,
                        valid_from=None,
                        supersedes_definition_id=supersedes,
                        description=f"Issuer-reported {category.value} observation from a disclosed XBRL dimension.",
                        known_at=document.known_at,
                        extraction_method=OPERATIONS_EXTRACTION_VERSION,
                        evidence_span_ids=[span.span_id],
                    )
                )
                self.repository.save_observation(
                    OperatingMetricObservationCreate(
                        definition_id=definition.definition_id,
                        period_start=fact.context.period_start,
                        period_end=fact.context.period_end,
                        fiscal_year=fact.context.period_end.year,
                        fiscal_period=self._fiscal_period(document.form, fact.context.period_start, fact.context.period_end),
                        value=fact.value,
                        unit=fact.unit,
                        known_at=document.known_at,
                        extraction_method=OPERATIONS_EXTRACTION_VERSION,
                        evidence_span_ids=[span.span_id],
                    )
                )
            except (LookupError, ValueError) as error:
                warnings.append(f"Operating fact {fact.concept} was not persisted: {error}")
        return self.repository.count_observations() - before, warnings

    def _classification(self, fact: ParsedXBRLFact) -> tuple[OperatingMetricCategory, str, str] | None:
        dimensions = fact.context.dimensions if fact.context else {}
        geography = self._matching_dimension(dimensions, self.geography_axis_tokens)
        if geography:
            axis, member = geography
            return OperatingMetricCategory.GEOGRAPHY, self._local(member), f"Inline XBRL {axis} / {member}"
        segment = self._matching_dimension(dimensions, self.segment_axis_tokens)
        if segment:
            axis, member = segment
            return OperatingMetricCategory.SEGMENT, self._local(member), f"Inline XBRL {axis} / {member}"
        concept_local = self._local(fact.concept)
        prefix = fact.concept.split(":", 1)[0].casefold() if ":" in fact.concept else ""
        if prefix not in {"us-gaap", "dei", "srt", "ifrs-full"} and any(
            token in concept_local.casefold() for token in self.kpi_tokens
        ):
            return OperatingMetricCategory.KPI, concept_local, f"Custom taxonomy concept {fact.concept}"
        return None

    @staticmethod
    def _matching_dimension(dimensions: dict[str, str], tokens: tuple[str, ...]) -> tuple[str, str] | None:
        for axis, member in dimensions.items():
            normalized_axis = re.sub(r"[^a-z0-9]", "", axis.casefold())
            if any(token in normalized_axis for token in tokens):
                return axis, member
        return None

    @classmethod
    def _measure(cls, concept: str) -> str:
        local = cls._local(concept).casefold()
        if "revenue" in local or "sales" in local:
            return "revenue"
        if "operatingincome" in local or "operatingprofit" in local:
            return "operating_income"
        if local.endswith("assets") or "assets" in local:
            return "assets"
        return cls._slug(cls._local(concept), 100)

    @classmethod
    def _definition_key(cls, category: OperatingMetricCategory, member: str, measure: str) -> str:
        return cls._slug(f"{category.value}.{member}.{measure}", 160)

    @staticmethod
    def _value_type(unit: str, concept: str) -> OperatingValueType:
        normalized = unit.casefold()
        if normalized == "usd" or normalized.startswith("usd/"):
            return OperatingValueType.CURRENCY
        if normalized in {"%", "percent", "percentage"}:
            return OperatingValueType.PERCENTAGE
        concept_local = OperationsDocumentExtractor._local(concept).casefold()
        if normalized == "ratio" and any(
            token in concept_local
            for token in ("subscriber", "user", "shipment", "location", "store", "employee", "seat", "units")
        ):
            return OperatingValueType.COUNT
        if normalized == "ratio":
            return OperatingValueType.RATIO
        if normalized in {"shares", "count"}:
            return OperatingValueType.COUNT
        return OperatingValueType.OTHER

    @staticmethod
    def _fiscal_period(form: str | None, period_start, period_end) -> str | None:
        if form and form.upper().startswith("10-Q"):
            return "Quarterly"
        if form and form.upper().startswith(("10-K", "20-F")):
            return "Annual"
        if period_start and (period_end - period_start).days < 150:
            return "Quarterly"
        return "Annual" if period_start else None

    @staticmethod
    def _local(value: str) -> str:
        return value.rsplit(":", 1)[-1].removesuffix("Member")

    @staticmethod
    def _label(value: str) -> str:
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value.replace("_", " ").replace("-", " "))
        return " ".join(part.capitalize() for part in spaced.split())

    @staticmethod
    def _slug(value: str, maximum: int) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value).casefold())
        normalized = normalized.strip("_")[:maximum].rstrip("_")
        return normalized or "reported_metric"


class GuidanceDocumentExtractor:
    guidance_marker = re.compile(r"\b(?:we\s+)?(?:expect|expects|expected|anticipate|project|forecast|guidance|outlook|intend|plan)\b", re.IGNORECASE)
    range_pattern = re.compile(
        r"(?P<low>\$?\d[\d,]*(?:\.\d+)?)\s*(?P<low_scale>billion|million|%)?\s*"
        r"(?:to|through|and|[-–])\s*"
        r"(?P<high>\$?\d[\d,]*(?:\.\d+)?)\s*(?P<high_scale>billion|million|%)?",
        re.IGNORECASE,
    )
    point_pattern = re.compile(r"(?P<value>\$?\d[\d,]*(?:\.\d+)?)\s*(?P<scale>billion|million|%)", re.IGNORECASE)
    period_pattern = re.compile(
        r"\b(?P<quarter>first|second|third|fourth|next)\s+quarter(?:\s+of)?(?:\s+fiscal)?\s*(?P<year>20\d{2})?",
        re.IGNORECASE,
    )
    metric_labels = {
        "revenue": ("Revenue Guidance", "revenue"),
        "gross margin": ("Gross Margin Guidance", "gross_margin"),
        "operating margin": ("Operating Margin Guidance", "operating_margin"),
        "operating expenses": ("Operating Expense Guidance", "operating_expenses"),
        "capital expenditures": ("Capital Expenditure Guidance", "capital_expenditures"),
        "free cash flow": ("Free Cash Flow Guidance", "free_cash_flow"),
        "earnings per share": ("Earnings Per Share Guidance", "diluted_eps"),
        "eps": ("Earnings Per Share Guidance", "diluted_eps"),
    }

    def __init__(self, repository: GuidanceRepository) -> None:
        self.repository = repository

    def extract(self, company_id: str, document: EvidenceDocument, spans: list[EvidenceSpan]) -> tuple[int, list[str]]:
        before = self.repository.count_statements()
        warnings = []
        for span in spans:
            for sentence in re.split(r"(?<=[.!?])\s+", span.exact_text):
                command = self._command(company_id, document, span, sentence.strip())
                if command is None:
                    continue
                try:
                    self.repository.save_statement(command)
                except (LookupError, ValueError) as error:
                    warnings.append(f"Guidance sentence was not persisted: {error}")
        return self.repository.count_statements() - before, warnings

    def _command(
        self,
        company_id: str,
        document: EvidenceDocument,
        span: EvidenceSpan,
        sentence: str,
    ) -> GuidanceStatementCreate | None:
        if len(sentence) < 20 or len(sentence) > 5000 or not self.guidance_marker.search(sentence):
            return None
        metric = next((value for key, value in self.metric_labels.items() if key in sentence.casefold()), None)
        period = self.period_pattern.search(sentence)
        fiscal_year = int(period.group("year")) if period and period.group("year") else None
        fiscal_period = self._quarter(period.group("quarter")) if period else None
        issued_at = document.published_at or document.filed_at or document.known_at
        if metric:
            topic, metric_id = metric
            range_match = self.range_pattern.search(sentence)
            if range_match:
                scale = range_match.group("high_scale") or range_match.group("low_scale")
                low, unit = self._normalized_number(range_match.group("low"), scale)
                high, high_unit = self._normalized_number(range_match.group("high"), scale)
                if unit != high_unit:
                    return None
                value_kind = GuidanceValueKind.NUMERIC_RANGE
                comparison = GuidanceComparison.WITHIN_RANGE
                lower_bound, upper_bound, point_value = min(low, high), max(low, high), None
            else:
                point_match = self.point_pattern.search(sentence)
                if not point_match:
                    return None
                point_value, unit = self._normalized_number(point_match.group("value"), point_match.group("scale"))
                value_kind = GuidanceValueKind.NUMERIC_POINT
                comparison = self._comparison(sentence)
                lower_bound = upper_bound = None
            statement_type = GuidanceStatementType.FINANCIAL_GUIDANCE
        else:
            if not re.search(r"\b(?:we\s+)?(?:expect|anticipate|intend|plan)\s+to\b", sentence, re.IGNORECASE):
                return None
            topic, metric_id = "Management Commitment", None
            value_kind = GuidanceValueKind.QUALITATIVE
            comparison = GuidanceComparison.NOT_APPLICABLE
            lower_bound = upper_bound = point_value = unit = None
            statement_type = GuidanceStatementType.STRATEGIC_COMMITMENT
        latest = self.repository.latest_comparable_statement(company_id, topic, metric_id, fiscal_year, fiscal_period)
        supersedes = None
        if latest and self._normalized_text(latest.statement_text) != self._normalized_text(sentence):
            supersedes = latest.statement_id
        return GuidanceStatementCreate(
            company_id=company_id,
            statement_type=statement_type,
            topic=topic,
            metric_id=metric_id,
            statement_text=sentence,
            value_kind=value_kind,
            comparison=comparison,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            point_value=point_value,
            unit=unit,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            issued_at=issued_at,
            known_at=document.known_at,
            extraction_method=GUIDANCE_EXTRACTION_VERSION,
            supersedes_statement_id=supersedes,
            evidence_span_ids=[span.span_id],
        )

    @staticmethod
    def _normalized_number(raw: str, scale: str | None) -> tuple[float, str]:
        value = float(raw.replace("$", "").replace(",", ""))
        normalized_scale = (scale or "").casefold()
        if normalized_scale == "billion":
            return value * 1000, "USD millions"
        if normalized_scale == "million":
            return value, "USD millions"
        if normalized_scale == "%":
            return value, "%"
        raise ValueError("Guidance numeric values require an explicit scale or percentage unit.")

    @staticmethod
    def _comparison(sentence: str) -> GuidanceComparison:
        normalized = sentence.casefold()
        if "at least" in normalized or "no less than" in normalized:
            return GuidanceComparison.AT_LEAST
        if "at most" in normalized or "up to" in normalized or "no more than" in normalized:
            return GuidanceComparison.AT_MOST
        return GuidanceComparison.APPROXIMATELY

    @staticmethod
    def _quarter(raw: str) -> str:
        return {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4", "next": "Next Quarter"}[raw.casefold()]

    @staticmethod
    def _normalized_text(value: str) -> str:
        return " ".join(value.casefold().split())


class DocumentExtractionService:
    evidence_keywords = re.compile(
        r"\b(customers?|suppliers?|foundr(?:y|ies)|manufacturers?|distributors?|partners?|competitors?|accounted\s+for|"
        r"purchas(?:e|es|ed|ing)\s+.{0,100}?\s+from|"
        r"rely|depends?|guidance|outlook|expect(?:s|ed)?|anticipat(?:e|es|ed)|forecast(?:s|ed)?|"
        r"project(?:s|ed)?|segment|geograph)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        evidence: EvidenceRepository,
        relationships: RelationshipService,
        operations: OperationsRepository,
        guidance: GuidanceRepository,
    ) -> None:
        self.evidence = evidence
        self.relationships = relationships
        self.operations = OperationsDocumentExtractor(operations)
        self.guidance = GuidanceDocumentExtractor(guidance)

    def extract(
        self,
        ticker: str,
        company_id: str,
        document: EvidenceDocument,
        parsed: ParsedEvidenceDocument,
    ) -> DocumentExtractionResult:
        block_indexes = {fact.block_index for fact in parsed.facts if fact.block_index is not None}
        block_indexes.update(
            index for index, block in enumerate(parsed.blocks) if self.evidence_keywords.search(block.text)
        )
        spans_by_block: dict[int, EvidenceSpan] = {}
        for index in sorted(block_indexes):
            block = parsed.blocks[index]
            spans_by_block[index] = self._save_block(document, block)
        fact_spans: dict[int, EvidenceSpan] = {}
        for index, fact in enumerate(parsed.facts):
            if fact.block_index is not None and fact.block_index in spans_by_block:
                fact_spans[index] = spans_by_block[fact.block_index]
                continue
            if fact.raw_value:
                fact_spans[index] = self.evidence.save_span(
                    EvidenceSpanCreate(
                        document_id=document.document_id,
                        exact_text=fact.raw_value,
                        start_offset=fact.start_offset,
                        end_offset=fact.end_offset,
                        extraction_method=DOCUMENT_PARSER_VERSION,
                        extracted_at=datetime.now(timezone.utc),
                        source_metadata={
                            "kind": "inline_xbrl_fact",
                            "concept": fact.concept,
                            "context_id": fact.context_id,
                            "dimensions": fact.context.dimensions if fact.context else {},
                        },
                    )
                )
        relationship_before = self.relationships.repository.count_observations()
        warnings = list(parsed.warnings)
        for span in spans_by_block.values():
            try:
                self.relationships.extract_span(ticker, span.span_id)
            except (LookupError, ValueError) as error:
                warnings.append(f"Relationship extraction skipped one evidence span: {error}")
        relationship_count = self.relationships.repository.count_observations() - relationship_before
        operating_count, operating_warnings = self.operations.extract(company_id, document, parsed, fact_spans)
        guidance_count, guidance_warnings = self.guidance.extract(company_id, document, list(spans_by_block.values()))
        warnings.extend(operating_warnings)
        warnings.extend(guidance_warnings)
        return DocumentExtractionResult(
            evidence_span_count=len({span.span_id for span in [*spans_by_block.values(), *fact_spans.values()]}),
            relationship_count=relationship_count,
            operating_observation_count=operating_count,
            guidance_statement_count=guidance_count,
            warnings=list(dict.fromkeys(warnings)),
        )

    def _save_block(self, document: EvidenceDocument, block: ParsedTextBlock) -> EvidenceSpan:
        return self.evidence.save_span(
            EvidenceSpanCreate(
                document_id=document.document_id,
                exact_text=block.text,
                section=block.section,
                start_offset=block.start_offset,
                end_offset=block.end_offset,
                extraction_method=DOCUMENT_PARSER_VERSION,
                extracted_at=datetime.now(timezone.utc),
                source_metadata={"kind": block.kind, "extractor_version": DOCUMENT_EXTRACTION_VERSION},
            )
        )
