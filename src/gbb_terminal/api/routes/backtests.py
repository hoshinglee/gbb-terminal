from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ...backtesting.engine import run_research_backtest
from ...backtesting.parameter_search import run_parameter_search
from ...backtesting.portfolio import run_ranked_portfolio
from ...backtesting.snapshots import create_snapshot_manifest
from ...market_data.service import MarketData
from ...storage.database import LocalMarketStore
from ...strategy.catalogue import StrategyCatalogue
from ...strategy.models import ResearchRun
from ..schemas.v2 import ParameterSearchRequest, ResearchRunRequest
from .shared import bad_request


def create_backtest_router(store: LocalMarketStore, data: MarketData, catalogue: StrategyCatalogue) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Research Runs"])

    @router.post("/research-runs")
    async def create_research_run(request: ResearchRunRequest):
        try:
            benchmark = request.strategy.benchmark.upper()
            if catalogue.is_portfolio(request.strategy.template_id):
                universe = list(dict.fromkeys(symbol.upper() for symbol in request.strategy.universe if symbol.strip()))
                if len(universe) < 2:
                    raise ValueError("A ranked portfolio requires at least two universe symbols.")
                loaded = await asyncio.gather(*(data.history(symbol, request.strategy.timeframe) for symbol in [*universe, benchmark]))
                histories = dict(zip(universe, loaded[:-1]))
                benchmark_history = loaded[-1]
                result = await asyncio.to_thread(run_ranked_portfolio, histories, benchmark_history, request.strategy)
                snapshot = create_snapshot_manifest({**histories, benchmark: benchmark_history})
            else:
                ticker = (request.strategy.ticker or "").upper()
                if not ticker:
                    raise ValueError("A ticker is required for an individual-stock research run.")
                comparison_symbols = list(dict.fromkeys([benchmark, "SPY", *([request.strategy.sector_benchmark.upper()] if request.strategy.sector_benchmark else [])]))
                peer_symbols = [symbol for symbol in request.strategy.universe if symbol not in {ticker, *comparison_symbols}]
                symbols = [ticker, *comparison_symbols, *peer_symbols]
                loaded = await asyncio.gather(*(data.history(symbol, request.strategy.timeframe) for symbol in symbols))
                loaded_histories = dict(zip(symbols, loaded))
                history = loaded_histories[ticker]
                comparisons = {symbol: loaded_histories[symbol] for symbol in comparison_symbols}
                peers = {symbol: loaded_histories[symbol] for symbol in peer_symbols}
                result = await asyncio.to_thread(
                    run_research_backtest,
                    history,
                    comparisons,
                    catalogue.build(request.strategy),
                    request.strategy.execution,
                    peer_histories=peers,
                )
                snapshot = create_snapshot_manifest(loaded_histories)
            research_run = ResearchRun(
                strategy=request.strategy,
                data_snapshot=snapshot,
                validation=request.validation,
                results=result,
            )
            payload = research_run.model_dump(mode="json")
            store.save_research_run(payload)
            return payload
        except ValueError as error:
            raise bad_request(error) from error

    @router.get("/research-runs/{run_id}")
    async def research_run(run_id: str):
        result = store.get_research_run(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Research run not found.")
        return result

    @router.post("/parameter-searches")
    async def parameter_search(request: ParameterSearchRequest):
        job_id = store.create_job("parameter_search", request.model_dump(mode="json"))
        try:
            ticker = (request.strategy.ticker or "").upper()
            if catalogue.is_portfolio(request.strategy.template_id):
                raise ValueError("Portfolio parameter search is not available in the initial guarded-search release.")
            if not ticker:
                raise ValueError("A ticker is required for parameter search.")
            comparison_symbols = list(dict.fromkeys([request.strategy.benchmark, "SPY", *([request.strategy.sector_benchmark] if request.strategy.sector_benchmark else [])]))
            peer_symbols = [symbol for symbol in request.strategy.universe if symbol not in {ticker, *comparison_symbols}]
            symbols = [ticker, *comparison_symbols, *peer_symbols]
            loaded = await asyncio.gather(*(data.history(symbol, request.strategy.timeframe) for symbol in symbols))
            loaded_histories = dict(zip(symbols, loaded))
            history = loaded_histories[ticker]
            benchmark = loaded_histories[request.strategy.benchmark]
            comparisons = {symbol: loaded_histories[symbol] for symbol in comparison_symbols}
            peers = {symbol: loaded_histories[symbol] for symbol in peer_symbols}
            result = await asyncio.to_thread(
                run_parameter_search,
                history,
                benchmark,
                request.strategy,
                request.ranges,
                catalogue,
                request.validation,
                request.max_trials,
                lambda progress: store.update_job(job_id, progress=progress),
                lambda: store.job_cancellation_requested(job_id),
                comparisons,
                peers,
            )
            best_strategy = request.strategy.model_validate(result["bestStrategy"])
            research_run = ResearchRun(
                strategy=best_strategy,
                data_snapshot=create_snapshot_manifest(loaded_histories),
                validation=request.validation,
                tested_parameters=result["attempts"],
                results=result["finalTest"],
            )
            store.save_research_run(research_run.model_dump(mode="json"))
            store.update_job(job_id, result=result)
            return {
                **result,
                "jobId": job_id,
                "runId": research_run.run_id,
                "reproducibilityKey": research_run.reproducibility_key,
            }
        except ValueError as error:
            store.update_job(job_id, error=str(error))
            raise bad_request(error) from error

    @router.get("/jobs/{job_id}")
    async def job(job_id: str):
        result = store.get_job(job_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return result

    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        if store.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="Research job not found.")
        return {"jobId": job_id, "cancelRequested": store.request_job_cancellation(job_id)}

    return router
