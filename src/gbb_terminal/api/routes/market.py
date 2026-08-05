from fastapi import APIRouter

from ...market_data.service import MarketData


def create_market_router(data: MarketData) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Market Data"])

    @router.get("/data-providers")
    async def providers():
        return {"providers": data.provider_statuses()}

    return router

