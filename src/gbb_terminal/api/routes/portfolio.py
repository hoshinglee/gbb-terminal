from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...portfolio.models import (
    PortfolioBundle,
    PortfolioContext,
    PortfolioContextInput,
    PortfolioPosition,
    PortfolioPositionInput,
    RiskPolicy,
    RiskPolicyInput,
    RiskPolicySnapshot,
)
from ...portfolio.service import PortfolioService


def create_portfolio_router(service: PortfolioService) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Portfolio Context"])

    @router.get("/portfolio-context", response_model=PortfolioBundle)
    async def portfolio_context() -> PortfolioBundle:
        return service.bundle()

    @router.put("/portfolio-context", response_model=PortfolioContext)
    async def update_portfolio_context(request: PortfolioContextInput) -> PortfolioContext:
        return service.save_context(request)

    @router.post(
        "/portfolio-context/positions",
        response_model=PortfolioPosition,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_portfolio_position(request: PortfolioPositionInput) -> PortfolioPosition:
        try:
            return service.create_position(request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/portfolio-context/positions/{position_id}", response_model=PortfolioPosition)
    async def update_portfolio_position(
        position_id: str,
        request: PortfolioPositionInput,
    ) -> PortfolioPosition:
        try:
            return service.update_position(position_id, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.delete("/portfolio-context/positions/{position_id}")
    async def delete_portfolio_position(position_id: str) -> dict[str, str]:
        if not service.delete_position(position_id):
            raise HTTPException(status_code=404, detail="Portfolio position was not found.")
        return {"deleted": position_id}

    @router.get("/risk-policy", response_model=RiskPolicy | None)
    async def current_risk_policy() -> RiskPolicy | None:
        return service.current_policy()

    @router.put("/risk-policy", response_model=RiskPolicy)
    async def update_risk_policy(request: RiskPolicyInput) -> RiskPolicy:
        return service.save_policy(request)

    @router.post(
        "/risk-policy/snapshots",
        response_model=RiskPolicySnapshot,
        status_code=status.HTTP_201_CREATED,
    )
    async def snapshot_risk_policy() -> RiskPolicySnapshot:
        try:
            return service.snapshot_policy()
        except LookupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/risk-policy/snapshots/{snapshot_id}", response_model=RiskPolicySnapshot)
    async def risk_policy_snapshot(snapshot_id: str) -> RiskPolicySnapshot:
        snapshot = service.policy_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Risk-policy snapshot was not found.")
        return snapshot

    return router
