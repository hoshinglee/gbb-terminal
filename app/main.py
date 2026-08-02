from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .market_data import MarketData
from .llm import GoogleAIStrategyTranslator
from .storage import LocalMarketStore
from .strategy import monte_carlo, run_backtest

store = LocalMarketStore(Path(__file__).parent.parent / "data" / "gbb_terminal.duckdb")
data = MarketData(store)
translator = GoogleAIStrategyTranslator()


async def refresh_cache() -> None:
    while True:
        await asyncio.sleep(900)
        for symbol in list(data.history_cache):
            try:
                await data.history(symbol)
            except ValueError:
                pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(refresh_cache())
    yield
    task.cancel()


app = FastAPI(title="GBB Terminal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class StrategyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    instruction: str = Field(min_length=8, max_length=500)
    window: str = Field(default="1y", pattern="^(1mo|3mo|6mo|1y|2y)$")


class SimulationRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    days: int = Field(default=252, ge=30, le=756)
    simulations: int = Field(default=400, ge=100, le=2000)


def fail(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/stock/{ticker}")
async def stock(ticker: str):
    try:
        quote, history = await data.quote(ticker), await data.history(ticker, "1y")
        chart = [{"date": index.strftime("%Y-%m-%d"), "close": round(float(row.Close), 2)} for index, row in history.tail(252).iterrows()]
        return {"quote": quote, "chart": chart}
    except ValueError as error:
        raise fail(error)


@app.get("/api/options/{ticker}")
async def options(ticker: str):
    try:
        return await data.options(ticker)
    except Exception as error:
        raise fail(error)


@app.post("/api/backtest")
async def backtest(request: StrategyRequest):
    try:
        translation = await asyncio.to_thread(translator.translate, request.instruction)
        history, spy_history = await asyncio.gather(
            data.history(request.ticker, request.window), data.history("SPY", request.window)
        )
        result = run_backtest(history, spy_history, translation.strategy)
        catalogue_item = store.save_strategy(request.instruction, result["strategy"], translation.provider)
        result["catalogueStrategy"] = catalogue_item
        result["runId"] = store.save_backtest(catalogue_item["id"], request.ticker.upper(), request.window, result["metrics"], result["trades"])
        result["window"] = request.window
        return result
    except ValueError as error:
        raise fail(error)


@app.get("/api/strategies")
async def strategies():
    return {"strategies": store.list_strategies()}


@app.get("/api/llm/status")
async def llm_status():
    return translator.status()


@app.post("/api/simulate")
async def simulate(request: SimulationRequest):
    try:
        return monte_carlo(await data.history(request.ticker), request.days, request.simulations)
    except ValueError as error:
        raise fail(error)


@app.get("/api/market-overview")
async def market_overview():
    try:
        return await data.dashboard()
    except ValueError as error:
        raise fail(error)
