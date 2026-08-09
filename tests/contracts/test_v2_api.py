from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.options import create_option_router
from gbb_terminal.api.routes.strategies import create_strategy_router
from gbb_terminal.llm.translator import GoogleAIStrategyTranslator
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.strategy.catalogue import catalogue


class UnusedMarketData:
    async def options(self, ticker, expiration=None):
        return {"symbol": ticker, "expiration": expiration, "expirations": [], "calls": [], "puts": []}


def test_v2_templates_and_option_simulation_contract(tmp_path):
    app = FastAPI()
    store = LocalMarketStore(tmp_path / "api.duckdb")
    app.include_router(create_strategy_router(store, GoogleAIStrategyTranslator(), catalogue))
    app.include_router(create_option_router(store, UnusedMarketData()))
    with TestClient(app) as client:
        templates = client.get("/api/v2/strategy-templates")
        assert templates.status_code == 200
        assert any(item["template_id"] == "darvas-volume-breakout" for item in templates.json()["templates"])
        option_templates = client.get("/api/v2/options/templates")
        assert option_templates.status_code == 200
        assert any(item["kind"] == "covered_call" for item in option_templates.json()["templates"])
        selected_chain = client.get("/api/v2/options/chains/NVDA?expiration=2028-12-15")
        assert selected_chain.status_code == 200
        assert selected_chain.json()["expiration"] == "2028-12-15"
        response = client.post("/api/v2/options/simulations", json={"ticker": "AAPL", "underlying_price": 100, "position_kind": "long_call", "paths": 50, "legs": [{"option_type": "call", "side": "long", "strike": 100, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 4, "quantity": 1, "implied_volatility": 0.25}]})
        assert response.status_code == 200
        assert response.json()["historicalStatus"] == "Theoretical Simulation"
        assert response.json()["runId"]
        runs = client.get("/api/v2/options/simulations")
        assert runs.status_code == 200
        assert runs.json()["runs"][0]["runId"] == response.json()["runId"]


def test_v2_option_position_lifecycle_contract(tmp_path):
    app = FastAPI()
    store = LocalMarketStore(tmp_path / "option-lifecycle.duckdb")
    app.include_router(create_option_router(store, UnusedMarketData()))
    position = {
        "name": "Paper Long Call",
        "ticker": "NVDA",
        "underlying_price": 180,
        "position_kind": "long_call",
        "paths": 50,
        "legs": [{"option_type": "call", "side": "long", "strike": 180, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium": 7, "quantity": 1, "implied_volatility": 0.3}],
    }
    with TestClient(app) as client:
        created = client.post("/api/v2/options/positions", json=position)
        assert created.status_code == 200
        payload = created.json()
        assert payload["position"]["status"] == "open"
        assert payload["events"][0]["eventType"] == "opened"
        position_id = payload["position"]["position_id"]
        positions = client.get("/api/v2/options/positions")
        assert positions.status_code == 200
        assert positions.json()["positions"][0]["position_id"] == position_id
        loaded = client.get(f"/api/v2/options/positions/{position_id}")
        assert loaded.status_code == 200
        assert loaded.json()["position"]["name"] == "Paper Long Call"
        held = client.post(f"/api/v2/options/positions/{position_id}/events", json={"event_type": "hold", "underlying_price": 185})
        assert held.status_code == 200
        assert held.json()["position"]["underlying_price"] == 185
        assert [event["eventType"] for event in held.json()["events"]] == ["opened", "hold"]
