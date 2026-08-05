from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ...backtesting.engine import run_research_backtest
from ...backtesting.parameter_search import run_parameter_search
from ...backtesting.portfolio import run_ranked_portfolio
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
                snapshot = {symbol: frame.index[-1].strftime("%Y-%m-%d") for symbol, frame in {**histories, benchmark: benchmark_history}.items()}
            else:
                ticker = (request.strategy.ticker or "").upper()
                if not ticker:
                    raise ValueError("A ticker is required for an individual-stock research run.")
                history, benchmark_history = await asyncio.gather(data.history(ticker, request.strategy.timeframe), data.history(benchmark, request.strategy.timeframe))
                result = await asyncio.to_thread(run_research_backtest, history, {benchmark: benchmark_history}, catalogue.build(request.strategy), request.strategy.execution)
                snapshot = {ticker: history.index[-1].strftime("%Y-%m-%d"), benchmark: benchmark_history.index[-1].strftime("%Y-%m-%d")}
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
            history, benchmark = await asyncio.gather(data.history(ticker, request.strategy.timeframe), data.history(request.strategy.benchmark, request.strategy.timeframe))
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
            )
            store.update_job(job_id, result=result)
            return {**result, "jobId": job_id}
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
