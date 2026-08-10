from __future__ import annotations

from dataclasses import dataclass

from ..intelligence.repository import CompanyIdentityRepository
from ..intelligence.service import CompanyIdentityService
from ..intelligence.fact_repository import FinancialFactRepository
from ..intelligence.fact_service import FinancialFactService
from ..intelligence.metrics import NormalizedMetricsService
from ..intelligence.company_service import CompanyIntelligenceService
from ..intelligence.valuation import HistoricalValuationService
from ..intelligence.valuation_repository import ValuationRepository
from ..llm.translator import StrategyTranslator
from ..market_data.service import MarketData
from ..settings import Settings, settings
from ..storage.database import LocalMarketStore
from ..strategy.catalogue import StrategyCatalogue, catalogue


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
    company_intelligence: CompanyIntelligenceService


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
    return ApplicationServices(
        store=store,
        market_data=market_data,
        translator=StrategyTranslator(configuration.llm),
        strategy_catalogue=catalogue,
        company_identity=company_identity,
        financial_facts=financial_facts,
        normalized_metrics=normalized_metrics,
        historical_valuation=historical_valuation,
        company_intelligence=CompanyIntelligenceService(
            company_identity,
            financial_facts,
            normalized_metrics,
            historical_valuation,
            market_data,
        ),
    )
