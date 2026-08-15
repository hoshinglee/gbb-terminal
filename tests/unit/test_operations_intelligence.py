import hashlib
from datetime import date, datetime, timezone

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    EvidenceDocumentCreate,
    EvidenceDocumentType,
    EvidenceRepository,
    EvidenceSpanCreate,
)
from gbb_terminal.intelligence.operations import OperationsIntelligenceService
from gbb_terminal.intelligence.operations_models import (
    OperatingIntelligenceQuery,
    OperatingMetricCategory,
    OperatingMetricDefinitionCreate,
    OperatingMetricObservationCreate,
    OperatingValueType,
)
from gbb_terminal.intelligence.operations_repository import OperationsRepository
from gbb_terminal.storage.database import LocalMarketStore


def build_services(tmp_path):
    store = LocalMarketStore(tmp_path / "operations.duckdb")
    identities = CompanyIdentityRepository(store.connection)
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    company = identities.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA Corporation",
            primary_ticker="NVDA",
            exchange="Nasdaq",
            effective_from=date(1999, 1, 22),
            provenance=CompanyProvenance(
                source="SEC EDGAR",
                dataset="sec_company_tickers",
                observation_timestamp=observed,
                known_at=observed,
                retrieved_at=observed,
            ),
        )
    )
    evidence = EvidenceRepository(store.connection)
    repository = OperationsRepository(store.connection, evidence)
    service = OperationsIntelligenceService(repository, evidence, CompanyIdentityService(identities, None))
    return company, evidence, repository, service


def create_span(evidence, company_id, text, known_at, external_id):
    document = evidence.save_document(
        EvidenceDocumentCreate(
            company_id=company_id,
            source="SEC EDGAR",
            dataset="sec_filing_documents",
            document_type=EvidenceDocumentType.FORM_10_K,
            external_id=external_id,
            title="Operating Disclosure",
            form="10-K",
            accession_number=external_id,
            source_url=f"https://www.sec.gov/Archives/{external_id}",
            filed_at=known_at,
            known_at=known_at,
            retrieved_at=known_at,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        )
    )
    return evidence.save_span(
        EvidenceSpanCreate(
            document_id=document.document_id,
            exact_text=text,
            section="Note 17. Segment Information",
            page_number=84,
            start_offset=0,
            end_offset=len(text),
            extraction_method="deterministic_fixture",
            extracted_at=known_at,
        )
    )


def save_definition(repository, company_id, span_id, known_at, key, label, basis, supersedes=None):
    return repository.save_definition(
        OperatingMetricDefinitionCreate(
            company_id=company_id,
            category=OperatingMetricCategory.SEGMENT,
            definition_key=key,
            label=label,
            measure="revenue",
            unit="USD",
            value_type=OperatingValueType.CURRENCY,
            reporting_basis=basis,
            supersedes_definition_id=supersedes,
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span_id],
        )
    )


def save_value(repository, definition_id, span_id, known_at, period_end, value):
    return repository.save_observation(
        OperatingMetricObservationCreate(
            definition_id=definition_id,
            period_end=period_end,
            fiscal_year=period_end.year,
            fiscal_period="FY",
            value=value,
            unit="USD",
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span_id],
        )
    )


def test_segment_reorganization_is_versioned_and_never_combined_for_growth(tmp_path):
    company, evidence, repository, service = build_services(tmp_path)
    old_known = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    old_span = create_span(
        evidence,
        company.company_id,
        "Gaming and Compute were the reportable revenue segments.",
        old_known,
        "0001045810-24-000010",
    )
    gaming_v1 = save_definition(repository, company.company_id, old_span.span_id, old_known, "gaming", "Gaming", "segments-v1")
    compute_v1 = save_definition(repository, company.company_id, old_span.span_id, old_known, "compute", "Compute", "segments-v1")
    for definition, first, second in ((gaming_v1, 40.0, 44.0), (compute_v1, 60.0, 66.0)):
        save_value(repository, definition.definition_id, old_span.span_id, old_known, date(2023, 1, 29), first)
        save_value(repository, definition.definition_id, old_span.span_id, old_known, date(2024, 1, 28), second)

    new_known = datetime(2025, 2, 21, 21, tzinfo=timezone.utc)
    new_span = create_span(
        evidence,
        company.company_id,
        "Data Center and Gaming are reported under a reorganized segment basis.",
        new_known,
        "0001045810-25-000010",
    )
    gaming_v2 = save_definition(
        repository,
        company.company_id,
        new_span.span_id,
        new_known,
        "gaming",
        "Gaming",
        "segments-v2",
        gaming_v1.definition_id,
    )
    compute_v2 = save_definition(
        repository,
        company.company_id,
        new_span.span_id,
        new_known,
        "compute",
        "Data Center And Compute",
        "segments-v2",
        compute_v1.definition_id,
    )
    save_value(repository, gaming_v2.definition_id, new_span.span_id, new_known, date(2025, 1, 26), 30.0)
    save_value(repository, compute_v2.definition_id, new_span.span_id, new_known, date(2025, 1, 26), 70.0)

    history = service.history("NVDA", OperatingIntelligenceQuery())
    compute_series_v1 = next(item for item in history.series if item.definition.definition_id == compute_v1.definition_id)
    compute_series_v2 = next(item for item in history.series if item.definition.definition_id == compute_v2.definition_id)

    assert compute_v2.version == 2
    assert compute_v2.supersedes_definition_id == compute_v1.definition_id
    assert len(history.transitions) == 2
    assert compute_series_v1.points[-1].growth_percent == 10
    assert compute_series_v1.points[-1].mix_percent == 60
    assert compute_series_v2.points[0].growth_percent is None
    assert compute_series_v2.points[0].mix_percent == 70
    assert "definitions changed" in " ".join(history.warnings)


def test_custom_kpi_and_issuer_geography_keep_typed_series_and_exact_labels(tmp_path):
    company, evidence, repository, service = build_services(tmp_path)
    known_at = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    span = create_span(
        evidence,
        company.company_id,
        "Paid subscribers reached 120 million. Revenue is reported for Americas Including United States.",
        known_at,
        "0001045810-24-000011",
    )
    subscribers = repository.save_definition(
        OperatingMetricDefinitionCreate(
            company_id=company.company_id,
            category=OperatingMetricCategory.KPI,
            definition_key="paid_subscribers",
            label="Paid Subscribers",
            measure="subscribers",
            unit="millions",
            value_type=OperatingValueType.COUNT,
            reporting_basis="subscriber-definition-v1",
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )
    )
    geography = repository.save_definition(
        OperatingMetricDefinitionCreate(
            company_id=company.company_id,
            category=OperatingMetricCategory.GEOGRAPHY,
            definition_key="americas_including_us",
            label="Americas Including United States",
            measure="revenue",
            unit="USD",
            value_type=OperatingValueType.CURRENCY,
            reporting_basis="issuer-geography-v1",
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )
    )
    for period_end, value in ((date(2023, 1, 29), 100.0), (date(2024, 1, 28), 120.0)):
        repository.save_observation(
            OperatingMetricObservationCreate(
                definition_id=subscribers.definition_id,
                period_end=period_end,
                fiscal_year=period_end.year,
                fiscal_period="FY",
                value=value,
                unit="millions",
                known_at=known_at,
                extraction_method="deterministic_fixture",
                evidence_span_ids=[span.span_id],
            )
        )
    repository.save_observation(
        OperatingMetricObservationCreate(
            definition_id=geography.definition_id,
            period_end=date(2024, 1, 28),
            fiscal_year=2024,
            fiscal_period="FY",
            value=50.0,
            unit="USD",
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )
    )

    history = service.history("NVDA", OperatingIntelligenceQuery())
    kpi = next(item for item in history.series if item.definition.category == OperatingMetricCategory.KPI)
    geography_series = next(
        item for item in history.series if item.definition.category == OperatingMetricCategory.GEOGRAPHY
    )

    assert kpi.definition.value_type == OperatingValueType.COUNT
    assert kpi.points[-1].growth_percent == 20
    assert kpi.points[-1].evidence[0].span.exact_text.startswith("Paid subscribers")
    assert geography_series.definition.label == "Americas Including United States"
    assert "non-standardized" in " ".join(history.warnings)


def test_unchanged_definition_accumulates_later_evidence_without_fake_version(tmp_path):
    company, evidence, repository, service = build_services(tmp_path)
    first_known = datetime(2024, 2, 21, 21, tzinfo=timezone.utc)
    first_span = create_span(
        evidence,
        company.company_id,
        "Gaming is a reportable revenue segment.",
        first_known,
        "0001045810-24-000012",
    )
    first = save_definition(
        repository,
        company.company_id,
        first_span.span_id,
        first_known,
        "gaming",
        "Gaming",
        "segments-v1",
    )
    later_known = datetime(2024, 5, 21, 21, tzinfo=timezone.utc)
    later_span = create_span(
        evidence,
        company.company_id,
        "Gaming remains a reportable revenue segment.",
        later_known,
        "0001045810-24-000013",
    )

    duplicate = save_definition(
        repository,
        company.company_id,
        later_span.span_id,
        later_known,
        "gaming",
        "Gaming",
        "segments-v1",
    )
    series = service.history("NVDA", OperatingIntelligenceQuery()).series[0]

    assert duplicate.definition_id == first.definition_id
    assert repository.count_definitions() == 1
    assert len(series.definition_evidence) == 2
