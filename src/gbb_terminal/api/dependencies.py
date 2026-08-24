from __future__ import annotations

from dataclasses import dataclass

from ..intelligence.repository import CompanyIdentityRepository
from ..intelligence.service import CompanyIdentityService
from ..intelligence.fact_repository import FinancialFactRepository
from ..intelligence.fact_service import FinancialFactService
from ..intelligence.metrics import NormalizedMetricsService
from ..intelligence.company_service import CompanyIntelligenceService
from ..intelligence.collection_repository import IntelligenceRefreshRepository
from ..intelligence.collection_service import IntelligenceRefreshService
from ..intelligence.collectors.sec import SECArchiveCollector
from ..intelligence.document_extraction import DocumentExtractionService
from ..intelligence.document_parser import PublicDocumentParser
from ..intelligence.earnings import EarningsIntelligenceService
from ..intelligence.earnings_repository import EarningsRepository
from ..intelligence.evidence import EvidenceService
from ..intelligence.evidence_repository import EvidenceRepository
from ..intelligence.estimates import EstimateIntelligenceService
from ..intelligence.guidance import GuidanceService
from ..intelligence.guidance_repository import GuidanceRepository
from ..intelligence.operations import OperationsIntelligenceService
from ..intelligence.operations_repository import OperationsRepository
from ..intelligence.relationship_repository import RelationshipRepository
from ..intelligence.relationships import RelationshipService
from ..intelligence.valuation import HistoricalValuationService
from ..intelligence.valuation_repository import ValuationRepository
from ..llm.translator import StrategyTranslator
from ..market_data.service import MarketData
from ..market_data.providers.estimates import EmptyEstimateProvider, ManualEstimateProvider
from ..portfolio.repository import PortfolioRepository
from ..portfolio.service import PortfolioService
from ..decision_center.repository import DecisionCenterRepository
from ..decision_center.service import DecisionCenterService
from ..settings import Settings, settings
from ..storage.database import LocalMarketStore
from ..strategy.catalogue import StrategyCatalogue, catalogue
from ..universe.providers import WikipediaSP500Provider
from ..universe.repository import UniverseRepository
from ..universe.service import UniverseResearchService


@dataclass(frozen=True)
class ApplicationServices:
    store: LocalMarketStore
    market_data: MarketData
    translator: StrategyTranslator
    strategy_catalogue: StrategyCatalogue
    company_identity: CompanyIdentityService
    financial_facts: FinancialFactService
    normalized_metrics: NormalizedMetricsService
    historical_valuation: HistoricalValuationService
    earnings_intelligence: EarningsIntelligenceService
    estimate_intelligence: EstimateIntelligenceService
    evidence_intelligence: EvidenceService
    relationship_intelligence: RelationshipService
    operations_intelligence: OperationsIntelligenceService
    guidance_intelligence: GuidanceService
    intelligence_refresh: IntelligenceRefreshService
    company_intelligence: CompanyIntelligenceService
    universe_research: UniverseResearchService
    portfolio_context: PortfolioService
    decision_center: DecisionCenterService


def build_services(configuration: Settings = settings) -> ApplicationServices:
    store = LocalMarketStore(configuration.database_path)
    market_data = MarketData(store)
    company_identity = CompanyIdentityService(CompanyIdentityRepository(store.connection), market_data.sec)
    financial_facts = FinancialFactService(
        FinancialFactRepository(store.connection),
        company_identity,
        store,
        market_data.sec,
    )
    normalized_metrics = NormalizedMetricsService(financial_facts, company_identity)
    historical_valuation = HistoricalValuationService(
        normalized_metrics,
        ValuationRepository(store.connection),
    )
    earnings_intelligence = EarningsIntelligenceService(
        normalized_metrics,
        EarningsRepository(store.connection),
    )
    estimate_provider = (
        ManualEstimateProvider.from_path(configuration.estimate_fixture_path)
        if configuration.estimate_fixture_path.exists()
        else EmptyEstimateProvider()
    )
    estimate_intelligence = EstimateIntelligenceService(
        normalized_metrics,
        estimate_provider,
    )
    evidence_repository = EvidenceRepository(store.connection)
    evidence_intelligence = EvidenceService(evidence_repository, company_identity)
    relationship_repository = RelationshipRepository(store.connection, evidence_repository)
    relationship_intelligence = RelationshipService(
        relationship_repository,
        evidence_repository,
        company_identity,
    )
    operations_repository = OperationsRepository(store.connection, evidence_repository)
    operations_intelligence = OperationsIntelligenceService(
        operations_repository,
        evidence_repository,
        company_identity,
    )
    guidance_repository = GuidanceRepository(store.connection, evidence_repository)
    guidance_intelligence = GuidanceService(
        guidance_repository,
        evidence_repository,
        company_identity,
        normalized_metrics,
    )
    intelligence_refresh = IntelligenceRefreshService(
        company_identity,
        evidence_repository,
        IntelligenceRefreshRepository(store.connection),
        SECArchiveCollector(market_data.sec),
        PublicDocumentParser(),
        DocumentExtractionService(
            evidence_repository,
            relationship_intelligence,
            operations_repository,
            guidance_repository,
        ),
        relationship_repository,
        operations_repository,
        guidance_repository,
    )
    company_intelligence = CompanyIntelligenceService(
        company_identity,
        financial_facts,
        normalized_metrics,
        historical_valuation,
        market_data,
        earnings_intelligence,
        estimate_intelligence,
        evidence_intelligence,
        relationship_intelligence,
        operations_intelligence,
        guidance_intelligence,
        intelligence_refresh,
    )
    universe_research = UniverseResearchService(
        UniverseRepository(store.connection),
        WikipediaSP500Provider(),
        company_identity,
        financial_facts,
        normalized_metrics,
        historical_valuation,
        earnings_intelligence,
        market_data,
    )
    portfolio_context = PortfolioService(
        PortfolioRepository(store.connection),
        company_identity,
    )
    decision_center = DecisionCenterService(
        DecisionCenterRepository(store.connection),
        company_identity,
        evidence_repository,
        portfolio_context,
    )
    return ApplicationServices(
        store=store,
        market_data=market_data,
        translator=StrategyTranslator(configuration.llm),
        strategy_catalogue=catalogue,
        company_identity=company_identity,
        financial_facts=financial_facts,
        normalized_metrics=normalized_metrics,
        historical_valuation=historical_valuation,
        earnings_intelligence=earnings_intelligence,
        estimate_intelligence=estimate_intelligence,
        evidence_intelligence=evidence_intelligence,
        relationship_intelligence=relationship_intelligence,
        operations_intelligence=operations_intelligence,
        guidance_intelligence=guidance_intelligence,
        intelligence_refresh=intelligence_refresh,
        company_intelligence=company_intelligence,
        universe_research=universe_research,
        portfolio_context=portfolio_context,
        decision_center=decision_center,
    )
