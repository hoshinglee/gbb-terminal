from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.decision_center import create_decision_center_router
from gbb_terminal.decision_center.repository import DecisionCenterRepository
from gbb_terminal.decision_center.service import DecisionCenterService
from gbb_terminal.intelligence.evidence_repository import EvidenceRepository
from gbb_terminal.intelligence.models import CompanyProvenance, CompanyRegistration
from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.portfolio.models import PortfolioContextInput, RiskPolicyInput
from gbb_terminal.portfolio.repository import PortfolioRepository
from gbb_terminal.portfolio.service import PortfolioService
from gbb_terminal.storage.database import LocalMarketStore


class UnavailableOptionsData:
    async def quote(self, ticker: str):
        return {"symbol": ticker, "price": 160}

    async def options(self, ticker: str, expiration: str | None = None):
        raise ValueError("No option chain fixture")


def client(tmp_path):
    store = LocalMarketStore(tmp_path / "decision-api.duckdb")
    identities = CompanyIdentityRepository(store.connection)
    identities.upsert_company(
        CompanyRegistration(
            cik="1045810",
            legal_name="NVIDIA Corporation",
            primary_ticker="NVDA",
            exchange="NASDAQ",
            provenance=CompanyProvenance.local("Decision API Fixture"),
        )
    )
    identity_service = CompanyIdentityService(identities, None)
    portfolio = PortfolioService(PortfolioRepository(store.connection), identity_service)
    portfolio.save_context(PortfolioContextInput(investable_value=200_000, liquid_cash=100_000))
    portfolio.save_policy(
        RiskPolicyInput(
            name="Personal Policy",
            normal_target_position_percent=10,
            max_single_name_exposure_percent=20,
            max_assignment_exposure_percent=20,
            max_short_option_collateral_percent=20,
            min_unencumbered_cash_reserve_amount=25_000,
            portfolio_stress_loss_ceiling_percent=20,
        )
    )
    service = DecisionCenterService(
        DecisionCenterRepository(store.connection),
        identity_service,
        EvidenceRepository(store.connection),
        portfolio,
    )
    app = FastAPI()
    app.include_router(create_decision_center_router(service, UnavailableOptionsData()))
    return TestClient(app), store


def test_decision_center_contract_supports_direct_share_chain_and_journal_review(tmp_path):
    api, store = client(tmp_path)
    with api:
        empty = api.get("/api/v2/decision-center/companies/NVDA")
        assert empty.status_code == 200
        assert empty.json()["thesis"] is None

        thesis = api.put(
            "/api/v2/decision-center/companies/NVDA/thesis",
            json={
                "status": "ready_for_position_planning",
                "evidence_strength": "moderate",
                "moat_assessment": "moderate",
                "major_risks": ["Cyclicality"],
                "catalysts": ["Product cycle"],
                "invalidation_criteria": ["Sustained demand decline"],
                "rationale": "Manual user-owned thesis.",
                "evidence_links": [],
            },
        )
        assert thesis.status_code == 200

        intent = api.put(
            "/api/v2/decision-center/companies/NVDA/position-intent",
            json={"target_percent": 10, "maximum_percent": 15, "current_price": 160},
        )
        assert intent.status_code == 200
        intent_id = intent.json()["intent_id"]

        comparison = api.post(
            "/api/v2/decision-center/companies/NVDA/expressions",
            json={
                "position_intent_id": intent_id,
                "objective": "ownership_now",
                "target_date": (date.today() + timedelta(days=45)).isoformat(),
                "share_price": 160,
            },
        )
        assert comparison.status_code == 200
        comparison_payload = comparison.json()
        assert comparison_payload["candidates"][0]["expression"]["kind"] == "direct_shares"
        assert "direct-share planning remains available" in comparison_payload["warnings"][0]
        expression = comparison_payload["candidates"][0]["expression"]

        plan = api.post(
            "/api/v2/decision-center/companies/NVDA/entry-plans",
            json={
                "position_intent_id": intent_id,
                "expression": expression,
                "execution_mode": "patient",
                "escape_plan": "abandon_wait",
                "tranches": [
                    {
                        "label": "Starter",
                        "allocation_percent": 40,
                        "preferred_entry_price": 155,
                        "maximum_acceptable_execution_price": 160,
                    },
                    {"label": "Reserve", "allocation_percent": 40, "status": "available"},
                ],
            },
        )
        assert plan.status_code == 201
        assert plan.json()["unallocated_reserve"] == 4_000

        stress = api.post(
            f"/api/v2/decision-center/companies/NVDA/stress-tests?position_intent_id={intent_id}",
            json={"expression": expression, "scenarios": [{"underlying_change_percent": -40}]},
        )
        assert stress.status_code == 200
        assert stress.json()["scenarios"][0]["position_pnl"] < 0

        decision = api.post(
            "/api/v2/decision-center/journal",
            json={
                "ticker": "NVDA",
                "decision_type": "ownership",
                "state": "missed",
                "thesis_id": thesis.json()["thesis_id"],
                "position_intent_id": intent_id,
                "expression": expression,
                "entry_plan_id": plan.json()["entry_plan_id"],
                "rationale": "The patient limit did not execute.",
            },
        )
        assert decision.status_code == 201
        decision_id = decision.json()["decision_id"]
        reviewed = api.put(
            f"/api/v2/decision-center/journal/{decision_id}",
            json={
                "state": "missed",
                "rationale": "The patient limit did not execute.",
                "process_review": {
                    "thesis_evidence_sufficient": "yes",
                    "position_inside_risk_budget": "yes",
                    "instrument_fit_intended_exposure": "yes",
                    "execution_followed_plan": "yes",
                    "exit_followed_rule": "not_applicable",
                    "process_quality": "good",
                    "notes": "Missing the trade did not invalidate the process.",
                },
                "later_outcome": {
                    "as_of": (date.today() + timedelta(days=30)).isoformat(),
                    "outcome": "favorable",
                    "return_percent": 18,
                    "description": "The stock later rallied.",
                },
            },
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["process_outcome_classification"] == "good_process_favorable_outcome"
        filtered = api.get("/api/v2/decision-center/journal?ticker=NVDA&review_status=reviewed")
        assert filtered.status_code == 200
        assert filtered.json()[0]["state"] == "missed"
    store.connection.close()
