from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.options import create_option_router
from gbb_terminal.api.routes.strategies import create_strategy_router
from gbb_terminal.llm.translator import GoogleAIStrategyTranslator
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.strategy.catalogue import catalogue


class UnusedMarketData:
    async def options(self, ticker):
        return {"symbol": ticker, "expirations": [], "calls": [], "puts": []}


def test_v2_templates_and_option_simulation_contract(tmp_path):
    app = FastAPI()
    store = LocalMarketStore(tmp_path / "api.duckdb")
    app.include_router(create_strategy_router(store, GoogleAIStrategyTranslator(), catalogue))
    app.include_router(create_option_router(store, UnusedMarketData()))
    with TestClient(app) as client:
        templates = client.get("/api/v2/strategy-templates")
        assert templates.status_code == 200
        assert any(item["template_id"] == "darvas-volume-breakout" for item in templates.json()["templates"])
        response = client.post("/api/v2/options/simulations", json={"ticker": "AAPL", "underlying_price": 100, "position_kind": "long_call", "paths": 50, "legs": [{"option_type": "call", "side": "long", "strike": 100, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 4, "quantity": 1, "implied_volatility": 0.25}]})
        assert response.status_code == 200
        assert response.json()["historicalStatus"] == "Theoretical Simulation"

