import hashlib
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

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
from gbb_terminal.intelligence.guidance import GuidanceService
from gbb_terminal.intelligence.guidance_models import (
    GuidanceComparison,
    GuidanceQuery,
    GuidanceRevisionDirection,
    GuidanceStatementCreate,
    GuidanceStatementType,
    GuidanceStatus,
    GuidanceValueKind,
    GuidanceWithdrawalCreate,
)
from gbb_terminal.intelligence.guidance_repository import GuidanceRepository
from gbb_terminal.storage.database import LocalMarketStore


def build_services(tmp_path):
    store = LocalMarketStore(tmp_path / "guidance.duckdb")
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
    repository = GuidanceRepository(store.connection, evidence)
    service = GuidanceService(repository, evidence, CompanyIdentityService(identities, None))
    return company, evidence, repository, service


def create_span(evidence, company_id, text, known_at, external_id):
    document = evidence.save_document(
        EvidenceDocumentCreate(
            company_id=company_id,
            source="SEC EDGAR",
            dataset="earnings_release_exhibit",
            document_type=EvidenceDocumentType.EARNINGS_RELEASE,
            external_id=external_id,
            title="Earnings Release",
            form="8-K",
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
            section="Outlook",
            page_number=2,
            start_offset=0,
            end_offset=len(text),
            extraction_method="deterministic_fixture",
            extracted_at=known_at,
        )
    )


def range_statement(company_id, span_id, known_at, text, low, high, supersedes=None):
    return GuidanceStatementCreate(
        company_id=company_id,
        statement_type=GuidanceStatementType.FINANCIAL_GUIDANCE,
        topic="Quarterly Revenue",
        metric_id="revenue",
        statement_text=text,
        value_kind=GuidanceValueKind.NUMERIC_RANGE,
        comparison=GuidanceComparison.WITHIN_RANGE,
        lower_bound=low,
        upper_bound=high,
        unit="USD millions",
        applicable_period_end=date(2025, 4, 27),
        fiscal_year=2026,
        fiscal_period="Q1",
        issued_at=known_at,
        known_at=known_at,
        extraction_method="deterministic_fixture",
        supersedes_statement_id=supersedes,
        evidence_span_ids=[span_id],
    )


def test_guidance_raises_cuts_and_withdrawal_preserve_immutable_revision_history(tmp_path):
    company, evidence, repository, service = build_services(tmp_path)
    first_known = datetime(2024, 11, 20, 21, tzinfo=timezone.utc)
    first_text = "Revenue is expected to be between $100 million and $110 million."
    first_span = create_span(evidence, company.company_id, first_text, first_known, "0001045810-24-000020")
    first = service.save_statement(
        range_statement(company.company_id, first_span.span_id, first_known, first_text, 100, 110)
    )

    raised_known = datetime(2025, 1, 10, 21, tzinfo=timezone.utc)
    raised_text = "Revenue is now expected to be between $120 million and $130 million."
    raised_span = create_span(evidence, company.company_id, raised_text, raised_known, "0001045810-25-000020")
    raised = service.save_statement(
        range_statement(
            company.company_id,
            raised_span.span_id,
            raised_known,
            raised_text,
            120,
            130,
            first.statement_id,
        )
    )

    cut_known = datetime(2025, 2, 10, 21, tzinfo=timezone.utc)
    cut_text = "Revenue is now expected to be between $90 million and $100 million."
    cut_span = create_span(evidence, company.company_id, cut_text, cut_known, "0001045810-25-000021")
    cut = service.save_statement(
        range_statement(
            company.company_id,
            cut_span.span_id,
            cut_known,
            cut_text,
            90,
            100,
            raised.statement_id,
        )
    )

    withdrawn_known = datetime(2025, 3, 1, 21, tzinfo=timezone.utc)
    withdrawn_text = "The company is withdrawing its previously issued quarterly revenue outlook."
    withdrawn_span = create_span(
        evidence,
        company.company_id,
        withdrawn_text,
        withdrawn_known,
        "0001045810-25-000022",
    )
    service.withdraw(
        "NVDA",
        cut.statement_id,
        GuidanceWithdrawalCreate(
            known_at=withdrawn_known,
            evidence_span_ids=[withdrawn_span.span_id],
            note="Management explicitly withdrew the outlook.",
        ),
    )

    history = service.history("NVDA", GuidanceQuery())
    records = {record.statement.statement_id: record for record in history.records}

    assert records[first.statement_id].revision_direction == GuidanceRevisionDirection.INITIAL
    assert records[raised.statement_id].revision_direction == GuidanceRevisionDirection.RAISED
    assert records[cut.statement_id].revision_direction == GuidanceRevisionDirection.CUT
    assert records[first.statement_id].status == GuidanceStatus.SUPERSEDED
    assert records[raised.statement_id].status == GuidanceStatus.SUPERSEDED
    assert records[cut.statement_id].status == GuidanceStatus.WITHDRAWN
    assert records[first.statement_id].statement.statement_text == first_text
    assert records[cut.statement_id].statement_evidence[0].span.exact_text == cut_text
    assert repository.count_statements() == 3
    assert repository.count_evaluations() == 3


def test_rule_based_outcomes_reconcile_numeric_bounds_and_reject_hidden_tolerance(tmp_path):
    company, evidence, _, service = build_services(tmp_path)
    known_at = datetime(2025, 2, 21, 21, tzinfo=timezone.utc)
    text = "Operating margin is expected to be between 20% and 22%."
    span = create_span(evidence, company.company_id, text, known_at, "0001045810-25-000023")
    statement = service.save_statement(
        GuidanceStatementCreate(
            company_id=company.company_id,
            statement_type=GuidanceStatementType.FINANCIAL_GUIDANCE,
            topic="Quarterly Operating Margin",
            metric_id="operating_margin",
            statement_text=text,
            value_kind=GuidanceValueKind.NUMERIC_RANGE,
            comparison=GuidanceComparison.WITHIN_RANGE,
            lower_bound=20,
            upper_bound=22,
            unit="%",
            applicable_period_end=date(2025, 4, 27),
            fiscal_year=2026,
            fiscal_period="Q1",
            issued_at=known_at,
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )
    )
    outcome_known = datetime(2025, 5, 21, 21, tzinfo=timezone.utc)
    outcome_span = create_span(
        evidence,
        company.company_id,
        "Reported operating margin for the quarter was 21%.",
        outcome_known,
        "0001045810-25-000024",
    )

    delivered = service.evaluate_numeric(
        "NVDA",
        statement.statement_id,
        actual_value=21,
        actual_unit="%",
        known_at=outcome_known,
        source_fact_ids=[],
        evidence_span_ids=[outcome_span.span_id],
    )

    assert delivered.status == GuidanceStatus.DELIVERED
    assert delivered.method.value == "rule_based"
    assert delivered.actual_value == 21

    approximate_text = "Capital expenditure is expected to be approximately $50 million."
    approximate_span = create_span(
        evidence,
        company.company_id,
        approximate_text,
        known_at,
        "0001045810-25-000025",
    )
    approximate = service.save_statement(
        GuidanceStatementCreate(
            company_id=company.company_id,
            statement_type=GuidanceStatementType.FINANCIAL_GUIDANCE,
            topic="Capital Expenditure",
            metric_id="capital_expenditure",
            statement_text=approximate_text,
            value_kind=GuidanceValueKind.NUMERIC_POINT,
            comparison=GuidanceComparison.APPROXIMATELY,
            point_value=50,
            unit="USD millions",
            applicable_period_end=date(2025, 4, 27),
            issued_at=known_at,
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[approximate_span.span_id],
        )
    )
    with pytest.raises(ValueError, match="manual tolerance"):
        service.evaluate_numeric(
            "NVDA",
            approximate.statement_id,
            actual_value=52,
            actual_unit="USD millions",
            known_at=outcome_known,
            source_fact_ids=[],
            evidence_span_ids=[outcome_span.span_id],
        )


def test_qualitative_commitments_cannot_receive_fabricated_numeric_precision(tmp_path):
    company, evidence, _, service = build_services(tmp_path)
    known_at = datetime(2025, 2, 21, 21, tzinfo=timezone.utc)
    text = "Management intends to diversify the supply base over time."
    span = create_span(evidence, company.company_id, text, known_at, "0001045810-25-000026")

    with pytest.raises(ValidationError, match="Qualitative guidance"):
        GuidanceStatementCreate(
            company_id=company.company_id,
            statement_type=GuidanceStatementType.STRATEGIC_COMMITMENT,
            topic="Supply Diversification",
            statement_text=text,
            value_kind=GuidanceValueKind.QUALITATIVE,
            comparison=GuidanceComparison.NOT_APPLICABLE,
            point_value=50,
            unit="%",
            issued_at=known_at,
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )

    statement = service.save_statement(
        GuidanceStatementCreate(
            company_id=company.company_id,
            statement_type=GuidanceStatementType.STRATEGIC_COMMITMENT,
            topic="Supply Diversification",
            statement_text=text,
            value_kind=GuidanceValueKind.QUALITATIVE,
            comparison=GuidanceComparison.NOT_APPLICABLE,
            issued_at=known_at,
            known_at=known_at,
            extraction_method="deterministic_fixture",
            evidence_span_ids=[span.span_id],
        )
    )

    assert statement.point_value is None
    assert service.history("NVDA", GuidanceQuery()).records[0].status == GuidanceStatus.OPEN
