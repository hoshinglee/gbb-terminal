from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..strategy.indicators.registry import IndicatorRegistry, technical_indicator_snapshot
from ..observability.logging import get_logger, log_event
from ..strategy.factory import StrategyFactory
from ..settings import settings
from ..backtesting.engine import run_research_backtest
from ..strategy.models import ExecutionAssumptions, StrategyInstance
from .dependencies import build_services
from .routes.backtests import create_backtest_router
from .routes.market import create_market_router
from .routes.options import create_option_router
from .routes.stocks import create_stock_router
from .routes.strategies import create_strategy_router

logger = get_logger("api")


def catalogue_strategy_definition(item: dict) -> dict:
    if item.get("strategyJson"):
        instance = StrategyInstance.from_catalogue_payload(item["strategyJson"])
        if catalogue.is_portfolio(instance.template_id):
            definition = {"strategy_type": "ranked_portfolio", "name": instance.name, "description": instance.description, "direction": "long", "parameters": instance.parameter_values}
            strategy_yaml = ""
        else:
            strategy = catalogue.build(instance)
            definition = strategy.spec().to_dict()
            strategy_yaml = strategy.to_yaml()
        return {
            "key": instance.semantic_key(),
            "definition": definition,
            "strategy_yaml": strategy_yaml,
            "strategy_json": instance.model_dump(mode="json"),
        }
    if item.get("strategyYaml"):
        strategy = StrategyFactory.from_yaml(item["strategyYaml"])
    else:
        strategy = StrategyFactory.create({"parameters": item["parameters"], "direction": item["direction"]})
    return {"key": StrategyFactory.strategy_key(strategy), "definition": strategy.spec().to_dict(), "strategy_yaml": strategy.to_yaml()}


services = build_services()
store = services.store
data = services.market_data
translator = services.translator
catalogue = services.strategy_catalogue
removed_duplicates = store.deduplicate_strategies(catalogue_strategy_definition)
log_event(logger, "application_initialized", removed_duplicate_strategies=removed_duplicates)


async def refresh_cache() -> None:
    while True:
        await asyncio.sleep(settings.refresh_interval_seconds)
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
app.mount("/static", StaticFiles(directory=settings.frontend_static_directory), name="static")
app.include_router(create_strategy_router(store, translator, catalogue))
app.include_router(create_backtest_router(store, data, catalogue))
app.include_router(create_option_router(store, data))
app.include_router(create_stock_router(data))
app.include_router(create_market_router(data))


@app.middleware("http")
async def request_logging_and_local_no_cache(request: Request, call_next):
    request_id, started = uuid4().hex[:12], perf_counter()
    if request.url.path in {"/", "/legacy"} or request.url.path.startswith("/static/"):
        request.scope["headers"] = [(name, value) for name, value in request.scope["headers"] if name.lower() not in {b"if-none-match", b"if-modified-since"}]
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("event=request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    if request.url.path in {"/", "/legacy"} or request.url.path.startswith("/static/"):
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
    benchmark: str = Field(default="SPY", min_length=1, max_length=12)
    commission_bps: float = Field(default=0.0, ge=0, le=100)
    slippage_bps: float = Field(default=0.0, ge=0, le=100)


class StrategyProposalRequest(BaseModel):
    instruction: str = Field(min_length=8, max_length=1000)


def fail(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@app.get("/")
async def index():
    return FileResponse(settings.frontend_index)


@app.get("/legacy")
async def legacy_index():
    return FileResponse(settings.frontend_legacy_index)


@app.get("/api/stock/{ticker}")
async def stock(ticker: str):
    try:
        quote, history = await data.quote(ticker), await data.history(ticker, "1y")
        chart = [{"date": index.strftime("%Y-%m-%d"), "open": round(float(row.Open), 2), "high": round(float(row.High), 2), "low": round(float(row.Low), 2), "close": round(float(row.Close), 2), "volume": int(row.Volume or 0)} for index, row in history.tail(252).iterrows()]
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
        benchmark_symbol = request.benchmark.upper()
        requested_symbols = [request.ticker.upper(), "SPY"] + ([benchmark_symbol] if benchmark_symbol != "SPY" else [])
        histories = await asyncio.gather(*(data.history(symbol, request.window) for symbol in requested_symbols))
        history, spy_history = histories[0], histories[1]
        benchmarks = {"SPY": spy_history}
        if benchmark_symbol != "SPY":
            benchmarks[benchmark_symbol] = histories[2]
        result = run_research_backtest(
            history,
            benchmarks,
            strategy,
            ExecutionAssumptions(commission_bps=request.commission_bps, slippage_bps=request.slippage_bps),
        )
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


@app.get("/api/market-overview")
async def market_overview():
    try:
        return await data.dashboard()
    except ValueError as error:
        raise fail(error)
