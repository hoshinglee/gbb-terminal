from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from gbb_terminal.intelligence.collection_models import (
    CollectorDiscovery,
    DiscoveredEvidenceDocument,
    IntelligenceRefreshRequest,
    IntelligenceRefreshStatus,
    ModuleCoverageStatus,
)
from gbb_terminal.intelligence.collection_repository import IntelligenceRefreshRepository
from gbb_terminal.intelligence.collection_service import IntelligenceRefreshService
from gbb_terminal.intelligence.collectors.base import EvidenceCollector
from gbb_terminal.intelligence.collectors.sec import SECArchiveCollector
from gbb_terminal.intelligence.document_extraction import DocumentExtractionService
from gbb_terminal.intelligence.document_parser import PublicDocumentParser
from gbb_terminal.intelligence.evidence_models import EvidenceDocumentType
from gbb_terminal.intelligence.evidence_repository import EvidenceRepository
from gbb_terminal.intelligence.guidance_repository import GuidanceRepository
from gbb_terminal.intelligence.models import CompanyProvenance, CompanyRegistration
from gbb_terminal.intelligence.operations_repository import OperationsRepository
from gbb_terminal.intelligence.operations_models import OperatingIntelligenceQuery, OperatingMetricCategory
from gbb_terminal.intelligence.relationship_repository import RelationshipRepository
from gbb_terminal.intelligence.relationships import RelationshipService
from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.market_data.models import DataEnvelope
from gbb_terminal.storage.database import LocalMarketStore


FIXTURES = Path(__file__).parents[1] / "fixtures" / "sec"
KNOWN_AT = datetime(2025, 5, 28, 20, 5, 32, tzinfo=timezone.utc)


class StaticCollector(EvidenceCollector):
    def __init__(self, documents: list[DiscoveredEvidenceDocument]) -> None:
        self.documents = documents
        self.downloads = 0

    def discover(self, company, request):
        return CollectorDiscovery(documents=self.documents)

    def download(self, company, document):
        self.downloads += 1
        return document.prefetched_content or b""


class StaticSECProvider:
    name = "SEC EDGAR"
    quality_warnings = []

    def submissions(self, cik):
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0001045810-25-000099"],
                    "filingDate": ["2025-05-28"],
                    "reportDate": ["2025-05-28"],
                    "acceptanceDateTime": ["2025-05-28T20:05:32Z"],
                    "form": ["8-K"],
                    "primaryDocument": ["nvda-20250528.htm"],
                    "primaryDocDescription": ["Current report"],
                    "items": ["2.02,9.01"],
                },
                "files": [],
            }
        }
        return DataEnvelope(
            "sec_submissions",
            "0001045810",
            payload,
            KNOWN_AT,
            KNOWN_AT,
            KNOWN_AT,
            "Delayed",
            self.name,
        )

    def filing_index_page(self, cik, accession):
        return (FIXTURES / "nvda_filing_index.html").read_bytes()

    def filing_document(self, cik, accession, document):
        if document == "nvda-ex991.htm":
            return (FIXTURES / "nvda_8k_exhibit.html").read_bytes()
        return b"<html><body><p>Current report filed with exhibit.</p></body></html>"

    @staticmethod
    def _filing_base(cik, accession):
        return "0001045810", f"https://www.sec.gov/Archives/edgar/data/1045810/{accession.replace('-', '')}"


def register_company(store: LocalMarketStore):
    repository = CompanyIdentityRepository(store.connection)
    observed = datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    company = repository.upsert_company(
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
    return company, repository


def discovered(external_id: str, filename: str, content: bytes, document_type: EvidenceDocumentType, form: str):
    return DiscoveredEvidenceDocument(
        source="SEC EDGAR",
        dataset="sec_filing_document",
        document_type=document_type,
        external_id=external_id,
        title=filename,
        form=form,
        accession_number=external_id.split(":", 1)[0],
        source_url=f"https://www.sec.gov/Archives/{filename}",
        filed_at=KNOWN_AT,
        published_at=KNOWN_AT,
        known_at=KNOWN_AT,
        mime_type="text/html",
        source_metadata={"archive_document": filename},
        prefetched_content=content,
    )


def build_refresh(tmp_path, collector):
    store = LocalMarketStore(tmp_path / "collection.duckdb")
    company, identity_repository = register_company(store)
    identities = CompanyIdentityService(identity_repository, None)
    evidence = EvidenceRepository(store.connection)
    relationships_repository = RelationshipRepository(store.connection, evidence)
    relationships = RelationshipService(relationships_repository, evidence, identities)
    operations = OperationsRepository(store.connection, evidence)
    guidance = GuidanceRepository(store.connection, evidence)
    service = IntelligenceRefreshService(
        identities,
        evidence,
        IntelligenceRefreshRepository(store.connection),
        collector,
        PublicDocumentParser(),
        DocumentExtractionService(evidence, relationships, operations, guidance),
        relationships_repository,
        operations,
        guidance,
    )
    return company, store, service, evidence, relationships_repository, operations, guidance


def test_sec_collector_discovers_filing_index_primary_and_relevant_exhibit():
    provider = StaticSECProvider()
    company = type("Company", (), {"cik": "0001045810"})()

    result = SECArchiveCollector(provider).discover(company, IntelligenceRefreshRequest(max_filings=1))

    assert {document.external_id for document in result.documents} == {
        "0001045810-25-000099:index",
        "0001045810-25-000099:nvda-20250528.htm",
        "0001045810-25-000099:nvda-ex991.htm",
    }
    exhibit = next(document for document in result.documents if document.external_id.endswith("nvda-ex991.htm"))
    assert exhibit.document_type == EvidenceDocumentType.EARNINGS_RELEASE
    assert exhibit.known_at == KNOWN_AT
    assert exhibit.source_metadata["archive_type"] == "EX-99.1"
    index = next(document for document in result.documents if document.external_id.endswith(":index"))
    assert index.source_url.endswith("0001045810-25-000099-index.htm")


def test_sec_collector_prioritizes_earnings_current_reports_before_newer_unrelated_filings():
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["newer-financing", "older-earnings"],
                "filingDate": ["2026-06-15", "2026-05-20"],
                "acceptanceDateTime": ["2026-06-15T20:00:00Z", "2026-05-20T20:00:00Z"],
                "form": ["8-K", "8-K"],
                "primaryDocument": ["financing.htm", "earnings.htm"],
                "primaryDocDescription": ["Current report", "Current report"],
                "items": ["1.01,9.01", "2.02,9.01"],
            },
            "files": [],
        }
    }

    rows = SECArchiveCollector(StaticSECProvider())._submission_rows(
        payload,
        {"8-K"},
        1,
        include_exhibits=True,
    )

    assert [row["accessionNumber"] for row in rows] == ["older-earnings"]


def test_parser_preserves_inline_xbrl_dimensions_and_custom_kpis():
    parsed = PublicDocumentParser().parse((FIXTURES / "nvda_10k_ixbrl.html").read_bytes(), "text/html")

    assert len(parsed.facts) == 3
    segment = next(fact for fact in parsed.facts if "seg-2025" == fact.context_id)
    geography = next(fact for fact in parsed.facts if "geo-2025" == fact.context_id)
    custom = next(fact for fact in parsed.facts if fact.concept == "nvda:ActiveDeveloperUsers")
    assert segment.value == 115_000_000_000
    assert segment.context.dimensions["srt:ProductOrServiceAxis"] == "nvda:ComputeAndNetworkingMember"
    assert geography.context.dimensions["srt:StatementGeographicalAxis"] == "nvda:UnitedStatesMember"
    assert custom.value == 4_200_000
    assert custom.context.period_end == date(2025, 1, 26)


def test_parser_keeps_leaf_div_narrative_in_table_heavy_inline_xbrl():
    table_rows = "".join(f"<tr><td>Metric {index}</td><td>{index}</td></tr>" for index in range(12))
    content = f"""
        <html><body>
          <table>{table_rows}</table>
          <div>We rely on Taiwan Semiconductor Manufacturing Company as our foundry.</div>
        </body></html>
    """.encode()

    parsed = PublicDocumentParser().parse(content, "text/html")

    assert any("Taiwan Semiconductor" in block.text for block in parsed.blocks)


def test_refresh_extracts_named_supply_chain_lists_from_real_disclosure_grammar(tmp_path):
    content = b"""
        <html><body><h2>Supply Chain</h2>
          <p>We utilize foundries, such as Taiwan Semiconductor Manufacturing Company Limited,
             or TSMC, and Samsung Electronics Co., Ltd., or Samsung, to produce our wafers.</p>
          <p>We purchase memory from SK Hynix Inc., Micron Technology, Inc., and Samsung.</p>
          <p>We engage contract manufacturers such as Hon Hai Precision Industry Co., Ltd.,
             Wistron Corporation, and Fabrinet to perform assembly and testing.</p>
        </body></html>
    """
    document = discovered(
        "0001045810-25-000021:supply-chain.htm",
        "supply-chain.htm",
        content,
        EvidenceDocumentType.FORM_10_K,
        "10-K",
    )
    company, _, service, _, relationships, *_ = build_refresh(tmp_path, StaticCollector([document]))

    result = service.refresh("NVDA", IntelligenceRefreshRequest(max_filings=1))
    edges = relationships.list_current(company.company_id, datetime(2026, 1, 1, tzinfo=timezone.utc))
    names = {edge.raw_counterparty_name for edge, _ in edges}

    assert result.relationship_count >= 6
    assert {
        "Taiwan Semiconductor Manufacturing Company Limited",
        "Samsung Electronics Co. Ltd",
        "SK Hynix Inc",
        "Micron Technology Inc",
        "Hon Hai Precision Industry Co. Ltd",
        "Wistron Corporation",
    } <= names


def test_relationship_lists_reject_product_categories_and_customer_purchase_grammar(tmp_path):
    content = b"""
        <html><body><h2>Supply Chain</h2>
          <p>Our suppliers, including CPUs, Ethernet, AI model makers, and Acme Semiconductor, Inc.</p>
          <p>Customers purchase our products from us but through multiple OEMs.</p>
        </body></html>
    """
    document = discovered(
        "0001045810-25-000022:generic-categories.htm",
        "generic-categories.htm",
        content,
        EvidenceDocumentType.FORM_10_K,
        "10-K",
    )
    company, _, service, _, relationships, *_ = build_refresh(tmp_path, StaticCollector([document]))

    result = service.refresh("NVDA", IntelligenceRefreshRequest(max_filings=1))
    edges = relationships.list_current(company.company_id, datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert result.relationship_count == 1
    assert [edge.raw_counterparty_name for edge, _ in edges] == ["Acme Semiconductor Inc"]


def test_refresh_populates_real_format_evidence_relationships_operations_and_guidance_idempotently(tmp_path):
    ten_k = discovered(
        "0001045810-25-000010:nvda-2025.htm",
        "nvda-2025.htm",
        (FIXTURES / "nvda_10k_ixbrl.html").read_bytes(),
        EvidenceDocumentType.FORM_10_K,
        "10-K",
    )
    exhibit = discovered(
        "0001045810-25-000099:nvda-ex991.htm",
        "nvda-ex991.htm",
        (FIXTURES / "nvda_8k_exhibit.html").read_bytes(),
        EvidenceDocumentType.EARNINGS_RELEASE,
        "8-K",
    )
    collector = StaticCollector([ten_k, exhibit])
    company, _, service, evidence, relationships, operations, guidance = build_refresh(tmp_path, collector)

    first = service.refresh("NVDA", IntelligenceRefreshRequest(max_filings=2))
    second = service.refresh("NVDA", IntelligenceRefreshRequest(max_filings=2))
    health = service.health("NVDA")

    assert first.status == IntelligenceRefreshStatus.COMPLETED
    assert first.documents_parsed == 2
    assert evidence.count_documents(company.company_id) == 2
    assert evidence.count_spans(company.company_id) >= 5
    assert relationships.count_company_observations(company.company_id) >= 2
    assert operations.count_company_observations(company.company_id) == 3
    assert guidance.count_company_statements(company.company_id) == 3
    assert second.documents_unchanged == 2
    assert second.documents_downloaded == 0
    assert collector.downloads == 2
    assert {item.status for item in health.coverage} == {ModuleCoverageStatus.POPULATED}
    assert health.last_refresh.refresh_id == second.refresh_id


def test_refresh_cancellation_preserves_completed_documents(tmp_path):
    documents = [
        discovered(
            f"0001045810-25-0000{index}:nvda-{index}.htm",
            f"nvda-{index}.htm",
            (FIXTURES / "nvda_8k_exhibit.html").read_bytes(),
            EvidenceDocumentType.EARNINGS_RELEASE,
            "8-K",
        )
        for index in range(1, 4)
    ]
    _, _, service, evidence, *_ = build_refresh(tmp_path, StaticCollector(documents))
    checks = iter([False, True])

    result = service.refresh("NVDA", cancelled=lambda: next(checks, True))

    assert result.status == IntelligenceRefreshStatus.CANCELLED
    assert result.documents_parsed == 1
    assert evidence.count_documents(result.company_id) == 1


def test_operating_extraction_uses_matching_axes_and_reuses_stable_definitions(tmp_path):
    document = discovered(
        "0001045810-25-000020:dimension-noise.htm",
        "dimension-noise.htm",
        (FIXTURES / "dimension_noise_ixbrl.html").read_bytes(),
        EvidenceDocumentType.FORM_10_K,
        "10-K",
    )
    company, _, service, _, _, operations, _ = build_refresh(tmp_path, StaticCollector([document]))

    result = service.refresh("NVDA", IntelligenceRefreshRequest(max_filings=1))
    definitions = operations.list_definitions(company.company_id, OperatingIntelligenceQuery())

    assert result.operating_observation_count == 3
    assert operations.count_definitions() == 2
    assert sum(definition.category == OperatingMetricCategory.SEGMENT for definition in definitions) == 1
    geography = next(definition for definition in definitions if definition.category == OperatingMetricCategory.GEOGRAPHY)
    assert geography.label == "United States Revenue"
    assert "StatementGeographicalAxis" in geography.reporting_basis
    assert not any("changed operating definition" in warning for warning in result.warnings)
