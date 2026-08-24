from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.portfolio import create_portfolio_router
from gbb_terminal.intelligence.models import CompanyProvenance, CompanyRegistration
from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.portfolio.repository import PortfolioRepository
from gbb_terminal.portfolio.service import PortfolioService
from gbb_terminal.storage.database import LocalMarketStore


def client(tmp_path):
    store = LocalMarketStore(tmp_path / "portfolio-api.duckdb")
    identities = CompanyIdentityRepository(store.connection)
    company = identities.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA Corporation",
            primary_ticker="NVDA",
            exchange="NASDAQ",
            effective_from=date(1999, 1, 22),
            provenance=CompanyProvenance.local("API Fixture"),
        )
    )
    service = PortfolioService(
        PortfolioRepository(store.connection),
        CompanyIdentityService(identities, None),
    )
    app = FastAPI()
    app.include_router(create_portfolio_router(service))
    return TestClient(app), store, company


def policy(max_position: float = 15) -> dict:
    return {
        "name": "Personal Risk Policy",
        "normal_target_position_percent": 8,
        "max_single_name_exposure_percent": max_position,
        "max_assignment_exposure_percent": 12,
        "max_short_option_collateral_percent": 20,
        "min_unencumbered_cash_reserve_amount": 80_000,
        "portfolio_stress_loss_ceiling_percent": 25,
    }


def test_portfolio_context_is_optional_and_manual_positions_resolve_identity(tmp_path):
    api, store, company = client(tmp_path)
    with api:
        empty = api.get("/api/v2/portfolio-context")
        assert empty.status_code == 200
        assert empty.json() == {"context": None, "positions": [], "risk_policy": None}

        context = api.put(
            "/api/v2/portfolio-context",
            json={"investable_value": 500_000, "liquid_cash": 150_000, "base_currency": "USD"},
        )
        assert context.status_code == 200

        created = api.post(
            "/api/v2/portfolio-context/positions",
            json={
                "ticker": "nvda",
                "shares": 100,
                "cost_basis_per_share": 140,
                "manual_market_value": 20_000,
                "notes": "Manual value survives provider outages.",
            },
        )
        assert created.status_code == 201
        position = created.json()
        assert position["ticker"] == "NVDA"
        assert position["company_id"] == company.company_id
        assert position["company_name"] == "NVIDIA Corporation"
        assert position["identity_status"] == "resolved"

        updated = api.put(
            f"/api/v2/portfolio-context/positions/{position['position_id']}",
            json={
                "ticker": "NVDA",
                "shares": 120,
                "cost_basis_per_share": 145,
                "manual_market_value": 24_000,
                "notes": "Updated manually.",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["shares"] == 120

        bundle = api.get("/api/v2/portfolio-context").json()
        assert bundle["positions"][0]["manual_market_value"] == 24_000
    store.connection.close()


def test_policy_updates_create_versions_and_snapshots_remain_immutable(tmp_path):
    api, store, _ = client(tmp_path)
    with api:
        first = api.put("/api/v2/risk-policy", json=policy()).json()
        snapshot = api.post("/api/v2/risk-policy/snapshots")
        second = api.put("/api/v2/risk-policy", json=policy(18)).json()

        assert first["version"] == 1
        assert snapshot.status_code == 201
        assert second["version"] == 2
        assert second["supersedes_policy_id"] == first["policy_id"]

        restored = api.get(f"/api/v2/risk-policy/snapshots/{snapshot.json()['snapshot_id']}")
        assert restored.status_code == 200
        assert restored.json()["policy_version"] == 1
        assert restored.json()["policy"]["max_single_name_exposure_percent"] == 15
    store.connection.close()
