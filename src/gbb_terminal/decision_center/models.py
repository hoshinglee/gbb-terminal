from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..options.models import OptionSimulationRequest
from ..portfolio.models import RiskPolicy


class DecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ThesisStatus(StrEnum):
    WATCH = "watch"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    READY_FOR_POSITION_PLANNING = "ready_for_position_planning"
    INVALIDATED = "invalidated"


class EvidenceStrength(StrEnum):
    UNKNOWN = "unknown"
    LIMITED = "limited"
    MODERATE = "moderate"
    STRONG = "strong"


class MoatAssessment(StrEnum):
    UNKNOWN = "unknown"
    NONE = "none"
    LIMITED = "limited"
    MODERATE = "moderate"
    STRONG = "strong"


class ThesisEvidenceLinkInput(DecisionModel):
    span_id: str = Field(min_length=1, max_length=128)
    role: Literal["support", "context", "contradiction"] = "support"
    interpretation: str = Field(default="", max_length=500)


class ThesisEvidenceReference(ThesisEvidenceLinkInput):
    document_id: str
    source: str
    source_url: str
    document_title: str | None = None
    exact_text: str
    known_at: datetime


class ThesisCardInput(DecisionModel):
    status: ThesisStatus = ThesisStatus.WATCH
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    moat_assessment: MoatAssessment = MoatAssessment.UNKNOWN
    major_risks: list[str] = Field(default_factory=list, max_length=20)
    catalysts: list[str] = Field(default_factory=list, max_length=20)
    invalidation_criteria: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(default="", max_length=5000)
    evidence_links: list[ThesisEvidenceLinkInput] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def ready_or_invalidated_has_invalidation_rule(self) -> "ThesisCardInput":
        if self.status in {ThesisStatus.READY_FOR_POSITION_PLANNING, ThesisStatus.INVALIDATED} and not any(
            item.strip() for item in self.invalidation_criteria
        ):
            raise ValueError("Ready or invalidated theses require at least one explicit invalidation criterion.")
        return self


class ThesisCard(DecisionModel):
    thesis_id: str
    thesis_key: str
    company_id: str
    ticker: str
    company_name: str
    version: int
    status: ThesisStatus
    evidence_strength: EvidenceStrength
    moat_assessment: MoatAssessment
    major_risks: list[str]
    catalysts: list[str]
    invalidation_criteria: list[str]
    rationale: str
    evidence_references: list[ThesisEvidenceReference]
    supersedes_thesis_id: str | None = None
    created_at: datetime


class ThesisSnapshot(DecisionModel):
    snapshot_id: str
    thesis_id: str
    thesis_version: int
    thesis: ThesisCard
    created_at: datetime


class PositionIntentInput(DecisionModel):
    target_amount: float | None = Field(default=None, gt=0)
    target_percent: float | None = Field(default=None, gt=0, le=100)
    maximum_amount: float | None = Field(default=None, gt=0)
    maximum_percent: float | None = Field(default=None, gt=0, le=100)
    current_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def target_and_maximum_are_defined(self) -> "PositionIntentInput":
        if self.target_amount is None and self.target_percent is None:
            raise ValueError("Define target position as an amount or percentage.")
        if self.maximum_amount is None and self.maximum_percent is None:
            raise ValueError("Define maximum position as an amount or percentage.")
        if self.target_amount is not None and self.maximum_amount is not None and self.target_amount > self.maximum_amount:
            raise ValueError("Target position amount cannot exceed maximum position amount.")
        if self.target_percent is not None and self.maximum_percent is not None and self.target_percent > self.maximum_percent:
            raise ValueError("Target position percentage cannot exceed maximum position percentage.")
        return self


class PositionIntent(DecisionModel):
    intent_id: str
    intent_key: str
    company_id: str
    ticker: str
    company_name: str
    version: int
    target_amount: float | None
    target_percent: float | None
    maximum_amount: float | None
    maximum_percent: float | None
    current_exposure_amount: float | None
    current_exposure_percent: float | None
    current_shares: float
    investable_value: float | None
    is_complete: bool
    warnings: list[str]
    supersedes_intent_id: str | None = None
    created_at: datetime


class PolicyCheck(DecisionModel):
    key: str
    label: str
    status: Literal["pass", "warn", "fail", "incomplete", "not_applicable"]
    actual: float | None = None
    limit: float | None = None
    unit: Literal["percent", "usd", "shares", "none"] = "none"
    arithmetic: str
    reason: str


class InstrumentExpression(DecisionModel):
    kind: Literal["direct_shares", "option"]
    name: str = Field(min_length=1, max_length=120)
    share_quantity: int | None = Field(default=None, ge=0)
    share_price: float | None = Field(default=None, gt=0)
    option_position: OptionSimulationRequest | None = None
    source_candidate_id: str | None = None

    @model_validator(mode="after")
    def expression_payload_matches_kind(self) -> "InstrumentExpression":
        if self.kind == "direct_shares" and self.share_price is None:
            raise ValueError("A direct-share expression requires a share price.")
        if self.kind == "option" and self.option_position is None:
            raise ValueError("An option expression requires a validated Option Lab position.")
        return self


class InstrumentFitResult(DecisionModel):
    candidate_id: str
    expression: InstrumentExpression
    overall_status: Literal["pass", "warn", "fail", "incomplete"]
    fit_label: str
    objective_fit: str
    current_exposure: float | None
    target_exposure: float | None
    maximum_exposure: float | None
    capital_required: float | None
    collateral_required: float | None
    assignment_obligation: float
    effective_acquisition_basis: float | None
    existing_shares: float
    shares_after_assignment: float | None
    post_assignment_exposure: float | None
    portfolio_footprint_percent: float | None
    cash_remaining: float | None
    maximum_loss: float | str | None
    break_evens: list[float]
    sizing_flexibility: str
    upside_character: str
    downside_character: str
    checks: list[PolicyCheck]
    arithmetic: list[str]
    warnings: list[str]


class PositionFitRequest(DecisionModel):
    position_intent_id: str
    expression: InstrumentExpression
    objective: Literal["ownership_now", "accumulate_lower", "income", "defined_risk_upside"] = "ownership_now"


class ExpressionComparisonRequest(DecisionModel):
    position_intent_id: str
    objective: Literal["ownership_now", "accumulate_lower", "income", "defined_risk_upside"]
    target_date: date
    target_price: float | None = Field(default=None, gt=0)
    share_price: float | None = Field(default=None, gt=0)


class ExpressionComparison(DecisionModel):
    ticker: str
    company_id: str
    objective: str
    generated_at: datetime
    position_intent: PositionIntent
    candidates: list[InstrumentFitResult]
    eligibility_notes: list[str]
    warnings: list[str]
    strategy_lab_url: str
    option_lab_url: str


class EntryTrancheInput(DecisionModel):
    label: str = Field(min_length=1, max_length=80)
    allocation_amount: float | None = Field(default=None, ge=0)
    allocation_percent: float | None = Field(default=None, ge=0, le=100)
    status: Literal["planned", "available", "used", "skipped", "cancelled"] = "planned"
    trigger: str = Field(default="", max_length=500)
    rationale: str = Field(default="", max_length=1000)
    preferred_entry_price: float | None = Field(default=None, gt=0)
    maximum_acceptable_execution_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def prices_are_ordered(self) -> "EntryTrancheInput":
        if (
            self.preferred_entry_price is not None
            and self.maximum_acceptable_execution_price is not None
            and self.preferred_entry_price > self.maximum_acceptable_execution_price
        ):
            raise ValueError("Preferred entry price cannot exceed the maximum acceptable execution price.")
        if self.allocation_amount is None and self.allocation_percent is None:
            raise ValueError("Each tranche requires an allocation amount or percentage.")
        return self


class EntryTranche(EntryTrancheInput):
    tranche_id: str
    resolved_allocation_amount: float
    resolved_allocation_percent: float | None


class EntryPlanInput(DecisionModel):
    position_intent_id: str
    expression: InstrumentExpression
    execution_mode: Literal["patient", "establish_exposure", "catalyst"]
    escape_plan: Literal["abandon_wait", "reassess_thesis", "allow_starter_within_maximum"]
    tranches: list[EntryTrancheInput] = Field(min_length=1, max_length=10)
    notes: str = Field(default="", max_length=3000)


class EntryPlan(DecisionModel):
    entry_plan_id: str
    plan_key: str
    company_id: str
    ticker: str
    company_name: str
    version: int
    position_intent_id: str
    expression: InstrumentExpression
    execution_mode: Literal["patient", "establish_exposure", "catalyst"]
    escape_plan: Literal["abandon_wait", "reassess_thesis", "allow_starter_within_maximum"]
    target_allocation_amount: float
    allocated_amount: float
    unallocated_reserve: float
    tranches: list[EntryTranche]
    notes: str
    supersedes_entry_plan_id: str | None = None
    created_at: datetime


class StressScenarioInput(DecisionModel):
    underlying_change_percent: float = Field(ge=-99, le=500)
    iv_change_percent: float = Field(default=0, ge=-90, le=500)
    days_forward: int = Field(default=0, ge=0, le=3650)


class StressTestRequest(DecisionModel):
    expression: InstrumentExpression
    scenarios: list[StressScenarioInput] = Field(
        default_factory=lambda: [
            StressScenarioInput(underlying_change_percent=-20),
            StressScenarioInput(underlying_change_percent=-40),
            StressScenarioInput(underlying_change_percent=-60),
        ],
        min_length=1,
        max_length=20,
    )


class StressScenarioResult(DecisionModel):
    scenario: StressScenarioInput
    stressed_underlying_price: float
    position_pnl: float
    portfolio_pnl_percent: float | None
    post_stress_single_name_percent: float | None
    cash_remaining: float | None
    assignment_obligation: float
    collateral_exposure: float
    checks: list[PolicyCheck]
    assumptions: list[str]
    warnings: list[str]


class StressTestResult(DecisionModel):
    ticker: str
    expression: InstrumentExpression
    generated_at: datetime
    scenarios: list[StressScenarioResult]
    limitations: list[str]


class ProcessReview(DecisionModel):
    thesis_evidence_sufficient: Literal["yes", "no", "not_applicable", "unreviewed"] = "unreviewed"
    position_inside_risk_budget: Literal["yes", "no", "not_applicable", "unreviewed"] = "unreviewed"
    instrument_fit_intended_exposure: Literal["yes", "no", "not_applicable", "unreviewed"] = "unreviewed"
    execution_followed_plan: Literal["yes", "no", "not_applicable", "unreviewed"] = "unreviewed"
    exit_followed_rule: Literal["yes", "no", "not_applicable", "unreviewed"] = "unreviewed"
    process_quality: Literal["good", "poor", "mixed", "unreviewed"] = "unreviewed"
    notes: str = Field(default="", max_length=5000)


class LaterOutcome(DecisionModel):
    as_of: date
    outcome: Literal["favorable", "unfavorable", "neutral", "unavailable"]
    return_percent: float | None = None
    description: str = Field(default="", max_length=3000)


class DecisionJournalCreate(DecisionModel):
    ticker: str = Field(min_length=1, max_length=12)
    decision_type: Literal["ownership", "accumulation", "income", "defined_risk", "risk_reduction", "pass"]
    state: Literal["planned", "entered", "partially_entered", "missed", "cancelled", "invalidated", "closed", "passed"]
    thesis_id: str | None = None
    position_intent_id: str | None = None
    expression: InstrumentExpression | None = None
    entry_plan_id: str | None = None
    rationale: str = Field(default="", max_length=5000)
    option_position_id: str | None = None
    actual_execution: dict[str, Any] = Field(default_factory=dict)


class DecisionJournalUpdate(DecisionModel):
    state: Literal["planned", "entered", "partially_entered", "missed", "cancelled", "invalidated", "closed", "passed"]
    rationale: str = Field(default="", max_length=5000)
    actual_execution: dict[str, Any] = Field(default_factory=dict)
    process_review: ProcessReview = Field(default_factory=ProcessReview)
    later_outcome: LaterOutcome | None = None


class DecisionJournalRecord(DecisionModel):
    decision_id: str
    revision: int
    company_id: str
    ticker: str
    company_name: str
    decision_type: str
    state: str
    thesis_snapshot: ThesisCard | None
    risk_policy_snapshot: RiskPolicy | None
    position_intent_snapshot: PositionIntent | None
    expression_snapshot: InstrumentExpression | None
    entry_plan_snapshot: EntryPlan | None
    rationale: str
    actual_execution: dict[str, Any]
    process_review: ProcessReview
    later_outcome: LaterOutcome | None
    process_outcome_classification: str | None
    option_position_id: str | None
    created_at: datetime
    updated_at: datetime


class DecisionJournalFilters(DecisionModel):
    ticker: str | None = None
    state: str | None = None
    decision_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    review_status: Literal["reviewed", "unreviewed"] | None = None


class DecisionCenterWorkspace(DecisionModel):
    company_id: str
    ticker: str
    company_name: str
    thesis: ThesisCard | None
    position_intent: PositionIntent | None
    entry_plans: list[EntryPlan]
    decisions: list[DecisionJournalRecord]
    risk_policy: RiskPolicy | None
