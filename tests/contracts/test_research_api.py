from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.backtests import create_backtest_router
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.strategy.catalogue import catalogue


class FixtureMarketData:
    def __init__(self, history):
        self.history_frame = history

    async def history(self, symbol, period):
        frame = self.history_frame.copy()
        if symbol.upper() != "AAPL":
            frame["Close"] *= 1.001
            frame["Open"] *= 1.001
            frame["High"] *= 1.001
            frame["Low"] *= 1.001
        return frame


def _client(tmp_path, price_history):
    app = FastAPI()
    store = LocalMarketStore(tmp_path / "research-api.duckdb")
    app.include_router(create_backtest_router(store, FixtureMarketData(price_history), catalogue))
    return TestClient(app), store


def test_research_run_contract_persists_data_and_reproducibility_identity(tmp_path, price_history):
    client, store = _client(tmp_path, price_history)
    strategy = catalogue.create_instance(
        "sma-crossover",
        {"fast_window": 5, "slow_window": 20},
        ticker="aapl",
        benchmark="spy",
        sector_benchmark="xlk",
        universe=["msft", "nvda"],
    )

    with client:
        response = client.post("/api/v2/research-runs", json={"strategy": strategy.model_dump(mode="json")})
        assert response.status_code == 200
        run = response.json()
        assert len(run["strategy_key"]) == 64
        assert len(run["reproducibility_key"]) == 64
        assert set(run["data_snapshot"]) == {"AAPL", "SPY", "XLK", "MSFT", "NVDA"}
        assert run["data_snapshot"]["AAPL"]["rows"] == len(price_history)
        assert set(run["results"]["metrics"]["benchmarkMetrics"]) >= {
            "Buy & Hold",
            "SPY",
            "XLK",
            "Equal-Weight Peers",
            "Exposure-Matched",
            "Volatility-Matched",
            "Cash",
        }
        restored = client.get(f"/api/v2/research-runs/{run['run_id']}")
        assert restored.status_code == 200
        assert restored.json()["reproducibility_key"] == run["reproducibility_key"]
        assert store.get_research_run(run["run_id"])["strategy_key"] == run["strategy_key"]


def test_parameter_search_contract_persists_final_holdout_run(tmp_path, price_history):
    client, store = _client(tmp_path, price_history)
    strategy = catalogue.create_instance("sma-crossover", {"fast_window": 5, "slow_window": 20}, ticker="AAPL")

    with client:
        response = client.post(
            "/api/v2/parameter-searches",
            json={
                "strategy": strategy.model_dump(mode="json"),
                "ranges": {"fast_window": [5, 10], "slow_window": [20, 30]},
                "max_trials": 4,
            },
        )
        assert response.status_code == 200
        search = response.json()
        assert search["finalTestWasUntouched"] is True
        assert search["finalTest"]["evaluationPeriod"]["start"] == search["finalTestStart"]
        assert len(search["reproducibilityKey"]) == 64
        persisted = store.get_research_run(search["runId"])
        assert persisted["tested_parameters"] == search["attempts"]
        assert persisted["results"] == search["finalTest"]


def test_v2_research_contract_rejects_unknown_fields(tmp_path, price_history):
    client, _ = _client(tmp_path, price_history)
    strategy = catalogue.create_instance("sma-crossover", ticker="AAPL").model_dump(mode="json")
    strategy["unsafe_extension"] = "ignored in older releases"

    with client:
        response = client.post("/api/v2/research-runs", json={"strategy": strategy})

    assert response.status_code == 422
