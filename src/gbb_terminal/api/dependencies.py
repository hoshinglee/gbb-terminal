from __future__ import annotations

from dataclasses import dataclass

from ..intelligence.repository import CompanyIdentityRepository
from ..intelligence.service import CompanyIdentityService
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


def build_services(configuration: Settings = settings) -> ApplicationServices:
    store = LocalMarketStore(configuration.database_path)
    market_data = MarketData(store)
    return ApplicationServices(
        store=store,
        market_data=market_data,
        translator=StrategyTranslator(configuration.llm),
        strategy_catalogue=catalogue,
        company_identity=CompanyIdentityService(CompanyIdentityRepository(store.connection), market_data.sec),
    )
