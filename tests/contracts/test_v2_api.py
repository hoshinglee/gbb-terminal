from datetime import date, timedelta

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.market import create_market_router
from gbb_terminal.api.routes.options import create_option_router
from gbb_terminal.api.routes.stocks import create_stock_router
from gbb_terminal.api.routes.strategies import create_strategy_router
from gbb_terminal.llm.translator import GoogleAIStrategyTranslator
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.strategy.catalogue import catalogue


class UnusedMarketData:
    async def options(self, ticker, expiration=None):
        return {"symbol": ticker, "expiration": expiration, "expirations": [], "calls": [], "puts": []}


class PlannerMarketData:
    def __init__(self):
        self.expiration = (date.today() + timedelta(days=60)).isoformat()
        self.metadata = {"NVDA": {"source": "Fixture"}}

    async def quote(self, ticker):
        return {"symbol": ticker.upper(), "price": 100, "dataStatus": {"source": "Fixture", "status": "Delayed"}}

    async def options(self, ticker, expiration=None):
        selected = expiration or self.expiration

        def contracts(option_type):
            return [
                {
                    "contract": f"{ticker.upper()}{option_type[0].upper()}{strike}",
                    "strike": strike,
                    "last": 4,
                    "bid": 3.8,
                    "ask": 4.2,
                    "mid": 4,
                    "volume": 50,
                    "openInterest": 200,
                    "iv": 30,
                    "quoteQuality": "Two-Sided",
                }
                for strike in (80, 90, 95, 100, 105, 110, 120)
            ]

        return {
            "expiration": selected,
            "defaultExpiration": self.expiration,
            "expirations": [self.expiration],
            "calls": contracts("call"),
            "puts": contracts("put"),
            "source": "Fixture",
            "dataStatus": {"source": "Fixture", "status": "Delayed", "qualityWarnings": []},
        }


class UnavailableEarningsIntelligence:
    async def earnings_history(self, *args, **kwargs):
        raise ValueError("SEC fixture is temporarily unavailable")


class ObservatoryMarketData:
    def __init__(self):
        self.updated_at = {}
        self.metadata = {}

    async def history(self, ticker, period):
        index = pd.date_range("2026-01-02", periods=80, freq="B")
        frame = pd.DataFrame({
            "Open": range(100, 180),
            "High": range(102, 182),
            "Low": range(98, 178),
            "Close": range(101, 181),
            "Volume": [1_000_000 + value * 1000 for value in range(80)],
        }, index=index)
        self.metadata[ticker.upper()] = {"source": "Fixture", "status": "Delayed", "knownAt": index[-1].isoformat()}
        return frame

    async def dashboard(self):
        status = {"source": "Fixture", "status": "Delayed", "knownAt": "2026-04-23T00:00:00"}
        return {
            "benchmark": {"symbol": "SPY", "name": "S&P 500 ETF", "price": 600, "change": 3, "changePercent": 0.5, "periodReturn": 4, "relativeStrength": None, "dataStatus": status, "available": True},
            "sectors": [{"symbol": "XLK", "name": "Technology", "price": 250, "change": 2, "changePercent": 0.8, "periodReturn": 7, "relativeStrength": 3, "dataStatus": status, "available": True}],
            "macro": [{"symbol": "^VIX", "name": "VIX", "price": 18, "change": -1, "changePercent": -5, "periodReturn": -2, "relativeStrength": None, "dataStatus": status, "available": True}],
        }

    def provider_statuses(self):
        return [{"provider": "Fixture", "configured": True, "status": "Delayed"}]


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


def test_v2_option_planner_and_scenario_contracts(tmp_path):
    app = FastAPI()
    store = LocalMarketStore(tmp_path / "option-planner.duckdb")
    app.include_router(create_option_router(store, PlannerMarketData(), UnavailableEarningsIntelligence()))
    target_date = (date.today() + timedelta(days=45)).isoformat()

    with TestClient(app) as client:
        planned = client.post("/api/v2/options/plans", json={
            "ticker": "NVDA",
            "outlook": "bullish",
            "target_date": target_date,
            "capital_budget": 2000,
        })
        assert planned.status_code == 200
        payload = planned.json()
        assert payload["ticker"] == "NVDA"
        assert payload["candidates"]
        assert all(candidate["positionKind"] != "short_call" for candidate in payload["candidates"])
        assert payload["candidates"][0]["quotes"][0]["bid"] == 3.8
        assert any("Historical earnings context is unavailable" in warning for warning in payload["warnings"])

        scenario = client.post("/api/v2/options/scenarios", json={
            "position": payload["candidates"][0]["position"],
            "scenario_price": 115,
            "scenario_date": target_date,
        })
        assert scenario.status_code == 200
        assert scenario.json()["scenarioPrice"] == 115
        assert scenario.json()["assumptions"]["model"] == "Cox-Ross-Rubinstein American Binomial"


def test_v2_stock_and_market_observability_contracts():
    app = FastAPI()
    data = ObservatoryMarketData()
    app.include_router(create_stock_router(data))
    app.include_router(create_market_router(data))

    with TestClient(app) as client:
        stock = client.get("/api/v2/stocks/NVDA?period=1y")
        assert stock.status_code == 200
        assert stock.json()["quote"]["symbol"] == "NVDA"
        assert set(stock.json()["marketChart"]["intervals"]) == {"day", "week", "month", "year"}
        five_year_stock = client.get("/api/v2/stocks/NVDA?period=5y")
        assert five_year_stock.status_code == 200
        unsupported_stock = client.get("/api/v2/stocks/NVDA?period=10y")
        assert unsupported_stock.status_code == 400
        market = client.get("/api/v2/market-overview")
        assert market.status_code == 200
        assert market.json()["sectors"][0]["symbol"] == "XLK"
        assert market.json()["providers"][0]["provider"] == "Fixture"
        assert market.json()["generatedAt"]
