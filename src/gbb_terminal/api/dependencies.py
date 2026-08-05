from __future__ import annotations

from dataclasses import dataclass

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


def build_services(configuration: Settings = settings) -> ApplicationServices:
    store = LocalMarketStore(configuration.database_path)
    return ApplicationServices(
        store=store,
        market_data=MarketData(store),
        translator=StrategyTranslator(configuration.llm),
        strategy_catalogue=catalogue,
    )
