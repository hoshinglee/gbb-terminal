from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .market_data import MarketData
from .indicators import IndicatorRegistry, technical_indicator_snapshot
from .llm import GoogleAIStrategyTranslator
from .logging_config import get_logger, log_event
from .storage import LocalMarketStore
from .strategy import StrategyFactory, monte_carlo, run_backtest

logger = get_logger("api")


def catalogue_strategy_definition(item: dict) -> dict:
    if item.get("strategyYaml"):
        strategy = StrategyFactory.from_yaml(item["strategyYaml"])
    else:
        strategy = StrategyFactory.create({"parameters": item["parameters"], "direction": item["direction"]})
    return {"key": StrategyFactory.strategy_key(strategy), "definition": strategy.spec().to_dict(), "strategy_yaml": strategy.to_yaml()}


store = LocalMarketStore(Path(__file__).parent.parent / "data" / "gbb_terminal.duckdb")
removed_duplicates = store.deduplicate_strategies(catalogue_strategy_definition)
data = MarketData(store)
translator = GoogleAIStrategyTranslator()
log_event(logger, "application_initialized", removed_duplicate_strategies=removed_duplicates)


async def refresh_cache() -> None:
    while True:
        await asyncio.sleep(900)
        for symbol in list(data.history_cache):
            try:
                await data.history(symbol)
            except ValueError as error:
                log_event(logger, "cache_refresh_failed", symbol=symbol, error=str(error))


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(refresh_cache())
    yield
    task.cancel()


app = FastAPI(title="GBB Terminal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def request_logging_and_local_no_cache(request: Request, call_next):
    request_id, started = uuid4().hex[:12], perf_counter()
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        request.scope["headers"] = [(name, value) for name, value in request.scope["headers"] if name.lower() not in {b"if-none-match", b"if-modified-since"}]
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("event=request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    log_event(logger, "request_completed", request_id=request_id, method=request.method, path=request.url.path, status=response.status_code, duration_ms=round((perf_counter() - started) * 1000, 2))
    return response


class StrategyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    instruction: str = Field(default="", max_length=1000)
    strategy_id: str | None = None
    strategy_yaml: str | None = Field(default=None, max_length=20_000)
    window: str = Field(default="1y", pattern="^(1mo|3mo|6mo|1y|2y)$")


class SimulationRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    days: int = Field(default=252, ge=30, le=756)
    simulations: int = Field(default=400, ge=100, le=2000)


class StrategyProposalRequest(BaseModel):
    instruction: str = Field(min_length=8, max_length=1000)


def fail(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/stock/{ticker}")
async def stock(ticker: str):
    try:
        quote, history = await data.quote(ticker), await data.history(ticker, "1y")
        chart = [{"date": index.strftime("%Y-%m-%d"), "close": round(float(row.Close), 2), "volume": int(row.Volume or 0)} for index, row in history.tail(252).iterrows()]
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
        if request.strategy_id:
            catalogue_item = store.get_strategy(request.strategy_id)
            if catalogue_item is None:
                raise ValueError("The selected catalogue strategy no longer exists.")
            strategy = StrategyFactory.from_yaml(catalogue_item["strategyYaml"]) if catalogue_item["strategyYaml"] else StrategyFactory.create({"parameters": catalogue_item["parameters"], "direction": catalogue_item["direction"]})
            instruction = catalogue_item["instruction"]
        elif request.strategy_yaml:
            strategy = StrategyFactory.from_yaml(request.strategy_yaml)
            instruction = request.instruction.strip() or strategy.spec().description
            strategy_key = StrategyFactory.strategy_key(strategy)
            catalogue_item = store.save_strategy(instruction, strategy.spec().to_dict(), "user_confirmed_llm", strategy.to_yaml(), strategy_key)
        else:
            if len(request.instruction.strip()) < 8:
                raise ValueError("Describe the strategy or load one from the catalogue.")
            translation = await asyncio.to_thread(translator.translate, request.instruction)
            strategy, instruction = translation.strategy, request.instruction
            strategy_key = StrategyFactory.strategy_key(strategy)
            catalogue_item = store.save_strategy(instruction, strategy.spec().to_dict(), translation.provider, translation.yaml_config, strategy_key)
        history, spy_history = await asyncio.gather(
            data.history(request.ticker, request.window), data.history("SPY", request.window)
        )
        result = run_backtest(history, spy_history, strategy)
        result["catalogueStrategy"] = catalogue_item
        result["runId"] = store.save_backtest(catalogue_item["id"], request.ticker.upper(), request.window, result["metrics"], result["trades"])
        result["window"] = request.window
        log_event(logger, "backtest_completed", run_id=result["runId"], strategy_key=catalogue_item["key"], ticker=request.ticker.upper(), window=request.window, closed_trades=result["metrics"]["trades"], open_trades=result["metrics"]["openTrades"])
        return result
    except ValueError as error:
        log_event(logger, "backtest_rejected", ticker=request.ticker.upper(), error=str(error))
        raise fail(error)


@app.post("/api/strategy/propose")
async def propose_strategy(request: StrategyProposalRequest):
    try:
        translation = await asyncio.to_thread(translator.translate, request.instruction)
        strategy_key = StrategyFactory.strategy_key(translation.strategy)
        existing = next((item for item in store.list_strategies() if item.get("key") == strategy_key), None)
        log_event(logger, "strategy_proposed", strategy_key=strategy_key, existing=bool(existing), clarifications=len(translation.clarifications))
        return {
            "strategy": translation.strategy.spec().to_dict(),
            "strategyYaml": translation.yaml_config,
            "strategyKey": strategy_key,
            "normalizedInstruction": translation.normalized_instruction,
            "clarifications": translation.clarifications,
            "needsConfirmation": translation.needs_confirmation,
            "existingStrategy": existing,
            "provider": translation.provider,
        }
    except ValueError as error:
        log_event(logger, "strategy_proposal_rejected", error=str(error))
        raise fail(error)


@app.get("/api/strategies")
async def strategies():
    return {"strategies": store.list_strategies()}


@app.get("/api/llm/status")
async def llm_status():
    return translator.status()


@app.get("/api/indicators")
async def indicator_catalogue():
    return {"indicators": IndicatorRegistry.catalogue()}


@app.get("/api/technical-indicators/{ticker}")
async def technical_indicators(ticker: str, period: str = "1y", indicators: str = "sma_20,ema_20,rsi_14,volume_sma_20"):
    try:
        if period not in {"1mo", "3mo", "6mo", "1y", "2y"}:
            raise ValueError("Period must be 1mo, 3mo, 6mo, 1y, or 2y.")
        history = await data.history(ticker, period)
        frame = technical_indicator_snapshot(history, [item.strip() for item in indicators.split(",") if item.strip()])
        return {"symbol": ticker.upper(), "period": period, "chart": [{"date": index.strftime("%Y-%m-%d"), **{column: round(float(value), 4) for column, value in row.items()}} for index, row in frame.iterrows()]}
    except ValueError as error:
        raise fail(error)


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
