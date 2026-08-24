from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from ...decision_center.models import (
    DecisionCenterWorkspace,
    DecisionJournalCreate,
    DecisionJournalFilters,
    DecisionJournalRecord,
    DecisionJournalUpdate,
    EntryPlan,
    EntryPlanInput,
    ExpressionComparison,
    ExpressionComparisonRequest,
    InstrumentFitResult,
    PositionFitRequest,
    PositionIntent,
    PositionIntentInput,
    StressTestRequest,
    StressTestResult,
    ThesisCard,
    ThesisCardInput,
    ThesisSnapshot,
)
from ...decision_center.service import DecisionCenterService
from ...market_data.service import MarketData
from ...options.models import OptionOutlook, OptionPlanRequest
from ...options.planner import build_option_plan, select_plan_expiration


def create_decision_center_router(service: DecisionCenterService, data: MarketData) -> APIRouter:
    router = APIRouter(prefix="/api/v2/decision-center", tags=["Decision Center"])

    @router.get("/companies/{ticker}", response_model=DecisionCenterWorkspace)
    async def workspace(ticker: str) -> DecisionCenterWorkspace:
        try:
            return service.workspace(ticker)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.get("/companies/{ticker}/thesis", response_model=ThesisCard | None)
    async def thesis(ticker: str) -> ThesisCard | None:
        try:
            return service.thesis(ticker)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.put("/companies/{ticker}/thesis", response_model=ThesisCard)
    async def save_thesis(ticker: str, request: ThesisCardInput) -> ThesisCard:
        try:
            return service.save_thesis(ticker, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post(
        "/companies/{ticker}/thesis/snapshots",
        response_model=ThesisSnapshot,
        status_code=status.HTTP_201_CREATED,
    )
    async def snapshot_thesis(ticker: str) -> ThesisSnapshot:
        try:
            return service.snapshot_thesis(ticker)
        except LookupError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/thesis-snapshots/{snapshot_id}", response_model=ThesisSnapshot)
    async def thesis_snapshot(snapshot_id: str) -> ThesisSnapshot:
        snapshot = service.thesis_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Thesis snapshot was not found.")
        return snapshot

    @router.get("/companies/{ticker}/position-intent", response_model=PositionIntent | None)
    async def position_intent(ticker: str) -> PositionIntent | None:
        try:
            return service.position_intent(ticker)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.put("/companies/{ticker}/position-intent", response_model=PositionIntent)
    async def save_position_intent(ticker: str, request: PositionIntentInput) -> PositionIntent:
        try:
            return service.save_position_intent(ticker, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/companies/{ticker}/fit-analysis", response_model=InstrumentFitResult)
    async def fit_analysis(ticker: str, request: PositionFitRequest) -> InstrumentFitResult:
        try:
            return service.analyze_fit(ticker, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/companies/{ticker}/expressions", response_model=ExpressionComparison)
    async def compare_expressions(ticker: str, request: ExpressionComparisonRequest) -> ExpressionComparison:
        try:
            intent = service.require_position_intent(ticker, request.position_intent_id)
            warnings: list[str] = []
            share_price = request.share_price
            if share_price is None:
                quote = await data.quote(ticker)
                share_price = float(quote["price"])
            option_candidates: list[dict] = []
            try:
                default_chain = await data.options(ticker)
                expiration, expiration_warnings = select_plan_expiration(
                    default_chain.get("expirations", []),
                    request.target_date,
                )
                selected_chain = (
                    default_chain
                    if default_chain.get("expiration") == expiration
                    else await data.options(ticker, expiration)
                )
                option_request = OptionPlanRequest(
                    ticker=ticker.strip().upper(),
                    outlook=OptionOutlook.NEUTRAL if request.objective == "income" else OptionOutlook.BULLISH,
                    target_date=request.target_date,
                    target_price=request.target_price,
                    shares_owned=max(int(intent.current_shares), 0),
                    acquiring_shares_acceptable=True,
                    maximum_loss=intent.maximum_amount,
                    capital_budget=intent.maximum_amount,
                )
                plan = await asyncio.to_thread(
                    build_option_plan,
                    option_request,
                    share_price,
                    selected_chain,
                    expiration_warnings,
                )
                option_candidates = plan["candidates"]
                warnings.extend(plan["warnings"])
            except Exception as error:
                warnings.append(
                    f"Current option comparison is unavailable; direct-share planning remains available. {error}"
                )
            return service.compare_expressions(
                ticker,
                request.position_intent_id,
                request.objective,
                share_price,
                option_candidates,
                warnings,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/companies/{ticker}/entry-plans", response_model=list[EntryPlan])
    async def entry_plans(ticker: str) -> list[EntryPlan]:
        try:
            return service.list_entry_plans(ticker)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.post(
        "/companies/{ticker}/entry-plans",
        response_model=EntryPlan,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_entry_plan(ticker: str, request: EntryPlanInput) -> EntryPlan:
        try:
            return service.save_entry_plan(ticker, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.put("/companies/{ticker}/entry-plans/{entry_plan_id}", response_model=EntryPlan)
    async def update_entry_plan(ticker: str, entry_plan_id: str, request: EntryPlanInput) -> EntryPlan:
        try:
            return service.save_entry_plan(ticker, request, prior_entry_plan_id=entry_plan_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/companies/{ticker}/stress-tests", response_model=StressTestResult)
    async def stress_test(
        ticker: str,
        request: StressTestRequest,
        position_intent_id: str = Query(min_length=1),
    ) -> StressTestResult:
        try:
            return service.stress_test(ticker, position_intent_id, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/journal", response_model=DecisionJournalRecord, status_code=status.HTTP_201_CREATED)
    async def create_decision(request: DecisionJournalCreate) -> DecisionJournalRecord:
        try:
            return service.create_decision(request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/journal", response_model=list[DecisionJournalRecord])
    async def decisions(
        ticker: str | None = None,
        state: str | None = None,
        decision_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        review_status: str | None = Query(default=None, pattern="^(reviewed|unreviewed)$"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[DecisionJournalRecord]:
        return service.decisions(
            DecisionJournalFilters(
                ticker=ticker,
                state=state,
                decision_type=decision_type,
                start_date=start_date,
                end_date=end_date,
                review_status=review_status,
            ),
            limit,
        )

    @router.get("/journal/{decision_id}", response_model=DecisionJournalRecord)
    async def decision(decision_id: str) -> DecisionJournalRecord:
        record = service.decision(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Decision journal record was not found.")
        return record

    @router.put("/journal/{decision_id}", response_model=DecisionJournalRecord)
    async def update_decision(decision_id: str, request: DecisionJournalUpdate) -> DecisionJournalRecord:
        try:
            return service.update_decision(decision_id, request)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.get("/journal/{decision_id}/revisions", response_model=list[DecisionJournalRecord])
    async def decision_revisions(decision_id: str) -> list[DecisionJournalRecord]:
        records = service.decision_revisions(decision_id)
        if not records:
            raise HTTPException(status_code=404, detail="Decision journal record was not found.")
        return records

    return router
