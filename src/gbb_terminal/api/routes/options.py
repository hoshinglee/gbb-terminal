from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException

from ...intelligence.company_service import CompanyIntelligenceService
from ...market_data.service import MarketData
from ...options.lifecycle import apply_event, initial_state
from ...options.models import (
    OptionLifecycleEvent,
    OptionPlanRequest,
    OptionPositionCreate,
    OptionScenarioRequest,
    OptionSimulationRequest,
    PositionLedgerState,
)
from ...options.planner import build_option_plan, scenario_position, select_plan_expiration
from ...options.simulation import simulate_position
from ...options.strategies import list_position_templates
from ...storage.database import LocalMarketStore
from .shared import bad_request


def create_option_router(
    store: LocalMarketStore,
    data: MarketData,
    company_intelligence: CompanyIntelligenceService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v2/options", tags=["Option Lab"])

    @router.get("/templates")
    async def templates():
        return {"templates": list_position_templates()}

    @router.get("/chains/{ticker}")
    async def chain(ticker: str, expiration: date | None = None):
        try:
            return await data.options(ticker, expiration.isoformat() if expiration else None)
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/plans")
    async def plan(request: OptionPlanRequest):
        try:
            quote, default_chain = await asyncio.gather(data.quote(request.ticker), data.options(request.ticker))
            expiration, warnings = select_plan_expiration(default_chain.get("expirations", []), request.target_date)
            selected_chain = default_chain if default_chain.get("expiration") == expiration else await data.options(request.ticker, expiration)
            earnings_context = None
            if company_intelligence is not None:
                try:
                    earnings = await company_intelligence.earnings_history(request.ticker, "SPY", None, 20)
                    earnings_context = {
                        "historicalMedianAbsoluteMovePercent": earnings.aggregate.typical_absolute_event_move,
                        "sampleSize": earnings.aggregate.sample_size,
                        "asOf": earnings.as_of.isoformat(),
                        "eventSource": "SEC EDGAR Company Facts",
                        "priceSource": data.metadata.get(request.ticker.upper(), {}).get("source", "Yahoo Finance"),
                        "warnings": earnings.warnings,
                        "interpretation": "Historical filing-event context only. It is not a forecast and does not identify option mispricing.",
                    }
                except Exception as error:
                    warnings.append(f"Historical earnings context is unavailable: {error}")
            return await asyncio.to_thread(
                build_option_plan,
                request,
                float(quote["price"]),
                selected_chain,
                warnings,
                earnings_context,
            )
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/scenarios")
    async def scenario(request: OptionScenarioRequest):
        try:
            return await asyncio.to_thread(scenario_position, request)
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/simulations")
    async def simulation(request: OptionSimulationRequest):
        try:
            result = await asyncio.to_thread(simulate_position, request)
            run = store.save_option_simulation_run(request.model_dump(mode="json"), result)
            return {**result, **run}
        except ValueError as error:
            raise bad_request(error) from error

    @router.get("/simulations")
    async def simulations(limit: int = 20):
        return {"runs": store.list_option_simulation_runs(limit)}

    @router.get("/simulations/{run_id}")
    async def stored_simulation(run_id: str):
        run = store.get_option_simulation_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Option simulation run not found.")
        return run

    @router.post("/positions")
    async def create_position(request: OptionPositionCreate):
        try:
            state = initial_state(request)
            store.create_option_position(state.model_dump(mode="json"))
            return {"position": state.model_dump(mode="json"), "events": store.list_option_events(state.position_id)}
        except ValueError as error:
            raise bad_request(error) from error

    @router.get("/positions")
    async def positions(limit: int = 20):
        return {"positions": store.list_option_positions(limit)}

    @router.get("/positions/{position_id}")
    async def position(position_id: str):
        state = store.get_option_position(position_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Option paper position not found.")
        return {"position": state, "events": store.list_option_events(position_id)}

    @router.post("/positions/{position_id}/events")
    async def position_event(position_id: str, event: OptionLifecycleEvent):
        stored = store.get_option_position(position_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Option paper position not found.")
        try:
            state = apply_event(PositionLedgerState.model_validate(stored), event)
            store.append_option_event(position_id, event.model_dump(mode="json"), state.model_dump(mode="json"))
            return {"position": state.model_dump(mode="json"), "events": store.list_option_events(position_id)}
        except ValueError as error:
            raise bad_request(error) from error

    return router
