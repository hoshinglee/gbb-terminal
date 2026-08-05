from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ...market_data.service import MarketData
from ...options.lifecycle import apply_event, initial_state
from ...options.models import OptionLifecycleEvent, OptionPositionCreate, OptionSimulationRequest, PositionLedgerState
from ...options.simulation import simulate_position
from ...options.strategies import list_position_templates
from ...storage.database import LocalMarketStore
from .shared import bad_request


def create_option_router(store: LocalMarketStore, data: MarketData) -> APIRouter:
    router = APIRouter(prefix="/api/v2/options", tags=["Option Lab"])

    @router.get("/templates")
    async def templates():
        return {"templates": list_position_templates()}

    @router.get("/chains/{ticker}")
    async def chain(ticker: str):
        try:
            return await data.options(ticker)
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/simulations")
    async def simulation(request: OptionSimulationRequest):
        try:
            return await asyncio.to_thread(simulate_position, request)
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/positions")
    async def create_position(request: OptionPositionCreate):
        try:
            state = initial_state(request)
            store.create_option_position(state.model_dump(mode="json"))
            return {"position": state.model_dump(mode="json"), "events": store.list_option_events(state.position_id)}
        except ValueError as error:
            raise bad_request(error) from error

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

