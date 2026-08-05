from __future__ import annotations

from fastapi import APIRouter

from ...market_data.service import MarketData
from ...strategy.indicators.registry import technical_indicator_snapshot
from .shared import bad_request


def create_stock_router(data: MarketData) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Stock Research"])

    @router.get("/chart-data")
    async def chart_data(ticker: str, period: str = "1y", indicators: str = "sma_20,volume_sma_20"):
        try:
            history = await data.history(ticker, period)
            requested = [value.strip() for value in indicators.split(",") if value.strip()]
            technical = technical_indicator_snapshot(history, requested).reindex(history.index)
            chart = []
            for index, row in history.iterrows():
                point = {"date": index.strftime("%Y-%m-%d"), "open": round(float(row.Open), 4), "high": round(float(row.High), 4), "low": round(float(row.Low), 4), "close": round(float(row.Close), 4), "volume": int(row.Volume or 0)}
                point["indicators"] = {name: round(float(technical.loc[index, name]), 4) for name in requested if name in technical and technical.loc[index, name] == technical.loc[index, name]}
                chart.append(point)
            return {"symbol": ticker.upper(), "period": period, "dataStatus": data.metadata.get(ticker.upper(), {}), "chart": chart}
        except ValueError as error:
            raise bad_request(error) from error

    return router

