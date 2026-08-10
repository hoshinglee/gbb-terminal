from __future__ import annotations

from dataclasses import dataclass

from ..intelligence.repository import CompanyIdentityRepository
from ..intelligence.service import CompanyIdentityService
from ..intelligence.fact_repository import FinancialFactRepository
from ..intelligence.fact_service import FinancialFactService
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


def build_services(configuration: Settings = settings) -> ApplicationServices:
    store = LocalMarketStore(configuration.database_path)
    market_data = MarketData(store)
    company_identity = CompanyIdentityService(CompanyIdentityRepository(store.connection), market_data.sec)
    return ApplicationServices(
        store=store,
        market_data=market_data,
        translator=StrategyTranslator(configuration.llm),
        strategy_catalogue=catalogue,
        company_identity=company_identity,
        financial_facts=FinancialFactService(
            FinancialFactRepository(store.connection),
            company_identity,
            store,
            market_data.sec,
        ),
    )
