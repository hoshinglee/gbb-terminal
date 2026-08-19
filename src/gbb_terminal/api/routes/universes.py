from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ...storage.database import LocalMarketStore
from ...universe.models import UniverseKey, UniverseRefreshRequest
from ...universe.service import UniverseResearchService
from ..schemas.v3 import (
    LocalJobResponse,
    SectorConstituentSnapshotResponse,
    UniverseCancelResponse,
    UniverseRefreshAcceptedResponse,
    UniverseRefreshRequestBody,
    UniverseStatusResponse,
)


def create_universe_router(
    service: UniverseResearchService,
    store: LocalMarketStore,
) -> APIRouter:
    router = APIRouter(prefix="/api/v3", tags=["Research Universes"])
    refresh_tasks: set[asyncio.Task] = set()

    @router.get("/universes/sp500", response_model=UniverseStatusResponse)
    async def sp500_status() -> UniverseStatusResponse:
        result = service.status(UniverseKey.SP500)
        payload = result.model_dump()
        if result.snapshot is not None:
            payload["snapshot"] = result.snapshot.model_dump(
                exclude={"constituents", "content_hash", "metadata"}
            )
        if result.latest_refresh is not None:
            payload["latest_refresh"] = result.latest_refresh.model_dump(exclude={"items"})
        return UniverseStatusResponse.model_validate(payload)

    @router.post(
        "/universes/sp500/refresh",
        response_model=UniverseRefreshAcceptedResponse,
        status_code=202,
    )
    async def refresh_sp500(
        request: UniverseRefreshRequestBody,
    ) -> UniverseRefreshAcceptedResponse:
        command = UniverseRefreshRequest.model_validate(request.model_dump())
        job_id = store.create_job(
            "sp500_universe_refresh",
            command.model_dump(mode="json"),
        )

        async def run_refresh() -> None:
            try:
                result = await service.refresh(
                    UniverseKey.SP500,
                    command,
                    lambda value, _: store.update_job(job_id, progress=value),
                    lambda: store.job_cancellation_requested(job_id),
                )
                final_status = (
                    "cancelled"
                    if result.status.value == "cancelled"
                    else "failed"
                    if result.status.value == "failed"
                    else "completed"
                )
                store.update_job(
                    job_id,
                    result=result.model_dump(mode="json"),
                    final_status=final_status,
                )
            except Exception as error:
                store.update_job(job_id, error=str(error))

        task = asyncio.create_task(run_refresh())
        refresh_tasks.add(task)
        task.add_done_callback(refresh_tasks.discard)
        return UniverseRefreshAcceptedResponse(job_id=job_id)

    @router.get(
        "/universes/sp500/sectors/{sector_symbol}/constituents",
        response_model=SectorConstituentSnapshotResponse,
    )
    async def sector_constituents(sector_symbol: str) -> SectorConstituentSnapshotResponse:
        try:
            result = service.sector_constituents(sector_symbol, UniverseKey.SP500)
            return SectorConstituentSnapshotResponse.model_validate(result.model_dump())
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/universe-jobs/{job_id}", response_model=LocalJobResponse)
    async def universe_job(job_id: str) -> LocalJobResponse:
        result = store.get_job(job_id)
        if result is None or result["jobType"] != "sp500_universe_refresh":
            raise HTTPException(status_code=404, detail="Universe refresh job not found.")
        return LocalJobResponse.model_validate(result)

    @router.post(
        "/universe-jobs/{job_id}/cancel",
        response_model=UniverseCancelResponse,
    )
    async def cancel_universe_job(job_id: str) -> UniverseCancelResponse:
        result = store.get_job(job_id)
        if result is None or result["jobType"] != "sp500_universe_refresh":
            raise HTTPException(status_code=404, detail="Universe refresh job not found.")
        return UniverseCancelResponse(
            job_id=job_id,
            cancel_requested=store.request_job_cancellation(job_id),
        )

    return router
