from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..intelligence.evidence_repository import EvidenceRepository
from ..intelligence.models import CompanyIdentity
from ..intelligence.service import CompanyIdentityService
from ..options.models import OptionSimulationRequest
from ..portfolio.service import PortfolioService
from .engine import analyze_expression, process_outcome_classification, stress_expression
from .models import (
    DecisionCenterWorkspace,
    DecisionJournalCreate,
    DecisionJournalFilters,
    DecisionJournalRecord,
    DecisionJournalUpdate,
    EntryPlan,
    EntryPlanInput,
    EntryTranche,
    ExpressionComparison,
    InstrumentExpression,
    InstrumentFitResult,
    PositionFitRequest,
    PositionIntent,
    PositionIntentInput,
    ProcessReview,
    StressTestRequest,
    StressTestResult,
    ThesisCard,
    ThesisCardInput,
    ThesisEvidenceReference,
    ThesisSnapshot,
)
from .repository import DecisionCenterRepository


class DecisionCenterService:
    def __init__(
        self,
        repository: DecisionCenterRepository,
        identities: CompanyIdentityService,
        evidence: EvidenceRepository,
        portfolio: PortfolioService,
    ) -> None:
        self.repository = repository
        self.identities = identities
        self.evidence = evidence
        self.portfolio = portfolio

    def workspace(self, ticker: str) -> DecisionCenterWorkspace:
        company = self._company(ticker)
        return DecisionCenterWorkspace(
            company_id=company.company_id,
            ticker=ticker.strip().upper(),
            company_name=company.legal_name,
            thesis=self.repository.current_thesis(company.company_id),
            position_intent=self.repository.current_intent(company.company_id),
            entry_plans=self.repository.list_entry_plans(company.company_id),
            decisions=self.repository.list_decisions(DecisionJournalFilters(ticker=ticker), limit=100),
            risk_policy=self.portfolio.current_policy(),
        )

    def thesis(self, ticker: str) -> ThesisCard | None:
        return self.repository.current_thesis(self._company(ticker).company_id)

    def save_thesis(self, ticker: str, value: ThesisCardInput) -> ThesisCard:
        company = self._company(ticker)
        references: list[ThesisEvidenceReference] = []
        seen: set[str] = set()
        for link in value.evidence_links:
            if link.span_id in seen:
                continue
            seen.add(link.span_id)
            span = self.evidence.get_span(link.span_id)
            document = self.evidence.get_document(span.document_id) if span else None
            if span is None or document is None or document.company_id != company.company_id:
                raise ValueError(
                    f"Evidence span {link.span_id} is not source evidence for {ticker.strip().upper()}."
                )
            references.append(
                ThesisEvidenceReference(
                    **link.model_dump(),
                    document_id=document.document_id,
                    source=document.source,
                    source_url=document.source_url,
                    document_title=document.title,
                    exact_text=span.exact_text,
                    known_at=document.known_at,
                )
            )
        return self.repository.save_thesis(
            company.company_id,
            ticker.strip().upper(),
            company.legal_name,
            value,
            references,
        )

    def snapshot_thesis(self, ticker: str) -> ThesisSnapshot:
        thesis = self.thesis(ticker)
        if thesis is None:
            raise LookupError("Create a Thesis Card before taking a snapshot.")
        return self.repository.snapshot_thesis(thesis)

    def thesis_snapshot(self, snapshot_id: str) -> ThesisSnapshot | None:
        return self.repository.thesis_snapshot(snapshot_id)

    def position_intent(self, ticker: str) -> PositionIntent | None:
        return self.repository.current_intent(self._company(ticker).company_id)

    def require_position_intent(self, ticker: str, intent_id: str) -> PositionIntent:
        company = self._company(ticker)
        return self._intent(intent_id, company.company_id)

    def save_position_intent(self, ticker: str, value: PositionIntentInput) -> PositionIntent:
        company = self._company(ticker)
        context = self.portfolio.repository.get_context()
        positions = self.portfolio.repository.list_positions()
        matching = [
            position
            for position in positions
            if position.company_id == company.company_id
            or (position.company_id is None and position.ticker == ticker.strip().upper())
        ]
        current_shares = sum(position.shares for position in matching)
        warnings: list[str] = []
        current_exposure = 0.0
        exposure_known = True
        for position in matching:
            if position.manual_market_value is not None:
                current_exposure += abs(position.manual_market_value)
            elif value.current_price is not None:
                current_exposure += abs(position.shares * value.current_price)
            else:
                exposure_known = False
        if not exposure_known:
            warnings.append(
                "Current exposure is incomplete because a holding has neither manual market value nor a supplied current price."
            )
        investable = context.investable_value if context else None
        target_amount, target_percent = self._resolve_amount_percent(
            value.target_amount,
            value.target_percent,
            investable,
            "target position",
        )
        maximum_amount, maximum_percent = self._resolve_amount_percent(
            value.maximum_amount,
            value.maximum_percent,
            investable,
            "maximum position",
        )
        if target_amount is not None and maximum_amount is not None and target_amount > maximum_amount:
            raise ValueError("Resolved target position cannot exceed resolved maximum position.")
        if context is None:
            warnings.append("Portfolio context is missing; percentage-to-amount and policy analysis may be incomplete.")
        current_amount = round(current_exposure, 2) if exposure_known else None
        current_percent = (
            round(current_exposure / investable * 100, 4)
            if exposure_known and investable is not None and investable > 0
            else None
        )
        current = self.repository.current_intent(company.company_id)
        intent = PositionIntent(
            intent_id=str(uuid4()),
            intent_key=f"company:{company.company_id}",
            company_id=company.company_id,
            ticker=ticker.strip().upper(),
            company_name=company.legal_name,
            version=(current.version + 1) if current else 1,
            target_amount=target_amount,
            target_percent=target_percent,
            maximum_amount=maximum_amount,
            maximum_percent=maximum_percent,
            current_exposure_amount=current_amount,
            current_exposure_percent=current_percent,
            current_shares=current_shares,
            investable_value=investable,
            is_complete=bool(
                context
                and target_amount is not None
                and maximum_amount is not None
                and current_amount is not None
            ),
            warnings=warnings,
            supersedes_intent_id=current.intent_id if current else None,
            created_at=self._utc_now(),
        )
        return self.repository.save_intent(intent)

    def analyze_fit(self, ticker: str, request: PositionFitRequest) -> InstrumentFitResult:
        company = self._company(ticker)
        intent = self._intent(request.position_intent_id, company.company_id)
        self._validate_expression_ticker(ticker, request.expression)
        return analyze_expression(
            intent,
            request.expression,
            self.portfolio.repository.get_context(),
            self.portfolio.current_policy(),
            request.objective,
        )

    def compare_expressions(
        self,
        ticker: str,
        position_intent_id: str,
        objective: str,
        share_price: float,
        option_candidates: list[dict],
        warnings: list[str],
    ) -> ExpressionComparison:
        company = self._company(ticker)
        intent = self._intent(position_intent_id, company.company_id)
        context = self.portfolio.repository.get_context()
        policy = self.portfolio.current_policy()
        expressions = [
            InstrumentExpression(
                kind="direct_shares",
                name="Direct Shares",
                share_price=share_price,
                source_candidate_id="direct-shares",
            )
        ]
        for candidate in option_candidates:
            expressions.append(
                InstrumentExpression(
                    kind="option",
                    name=str(candidate["name"]),
                    option_position=OptionSimulationRequest.model_validate(candidate["position"]),
                    source_candidate_id=str(candidate["candidateId"]),
                )
            )
        results = [analyze_expression(intent, expression, context, policy, objective) for expression in expressions]
        eligibility_notes = []
        if intent.current_shares < 100:
            eligibility_notes.append(
                f"Covered call unavailable: {intent.current_shares:g} existing shares; 100 shares are required per standard short-call contract."
            )
        else:
            eligibility_notes.append(
                f"Covered call eligible from share ownership: {intent.current_shares:g} existing shares support {int(intent.current_shares // 100)} standard contract(s)."
            )
        query = f"ticker={ticker.strip().upper()}&desiredExposure={intent.target_amount or ''}&objective={objective}"
        return ExpressionComparison(
            ticker=ticker.strip().upper(),
            company_id=company.company_id,
            objective=objective,
            generated_at=datetime.now(timezone.utc),
            position_intent=intent,
            candidates=results,
            eligibility_notes=eligibility_notes,
            warnings=warnings,
            strategy_lab_url=f"/?{query}",
            option_lab_url=f"/?lab=options&{query}",
        )

    def save_entry_plan(
        self,
        ticker: str,
        value: EntryPlanInput,
        *,
        prior_entry_plan_id: str | None = None,
    ) -> EntryPlan:
        company = self._company(ticker)
        intent = self._intent(value.position_intent_id, company.company_id)
        self._validate_expression_ticker(ticker, value.expression)
        if intent.target_amount is None:
            raise ValueError("Resolve a target position amount before building an entry plan.")
        prior = None
        if prior_entry_plan_id:
            prior = self.repository.entry_plan(prior_entry_plan_id)
            if prior is None or prior.company_id != company.company_id:
                raise LookupError("Entry plan was not found for this company.")
        tranches: list[EntryTranche] = []
        for item in value.tranches:
            amount = item.allocation_amount
            if amount is None:
                amount = intent.target_amount * float(item.allocation_percent or 0) / 100
            percent = item.allocation_percent
            if percent is None:
                percent = amount / intent.target_amount * 100 if intent.target_amount else None
            if item.allocation_amount is not None and item.allocation_percent is not None:
                expected = intent.target_amount * item.allocation_percent / 100
                if abs(expected - item.allocation_amount) > max(1, intent.target_amount * 0.001):
                    raise ValueError(f"{item.label} amount and percentage do not reconcile to the saved target.")
            tranches.append(
                EntryTranche(
                    **item.model_dump(),
                    tranche_id=str(uuid4()),
                    resolved_allocation_amount=round(amount, 2),
                    resolved_allocation_percent=round(percent, 4) if percent is not None else None,
                )
            )
        allocated = sum(tranche.resolved_allocation_amount for tranche in tranches)
        if allocated > intent.target_amount + 0.01:
            raise ValueError("Entry-plan tranches cannot exceed the intended target position.")
        return self.repository.save_entry_plan(
            company.company_id,
            ticker.strip().upper(),
            company.legal_name,
            value,
            tranches,
            intent.target_amount,
            prior=prior,
        )

    def entry_plan(self, entry_plan_id: str) -> EntryPlan | None:
        return self.repository.entry_plan(entry_plan_id)

    def list_entry_plans(self, ticker: str) -> list[EntryPlan]:
        return self.repository.list_entry_plans(self._company(ticker).company_id)

    def stress_test(self, ticker: str, position_intent_id: str, request: StressTestRequest) -> StressTestResult:
        company = self._company(ticker)
        intent = self._intent(position_intent_id, company.company_id)
        self._validate_expression_ticker(ticker, request.expression)
        return stress_expression(
            ticker.strip().upper(),
            intent,
            request,
            self.portfolio.repository.get_context(),
            self.portfolio.current_policy(),
        )

    def create_decision(self, value: DecisionJournalCreate) -> DecisionJournalRecord:
        company = self._company(value.ticker)
        thesis = self.repository.thesis(value.thesis_id) if value.thesis_id else self.repository.current_thesis(company.company_id)
        intent = self.repository.intent(value.position_intent_id) if value.position_intent_id else self.repository.current_intent(company.company_id)
        entry_plan = self.repository.entry_plan(value.entry_plan_id) if value.entry_plan_id else None
        for snapshot in [thesis, intent, entry_plan]:
            if snapshot is not None and snapshot.company_id != company.company_id:
                raise ValueError("Decision snapshots must belong to the selected canonical company.")
        expression = value.expression or (entry_plan.expression if entry_plan else None)
        if expression:
            self._validate_expression_ticker(value.ticker, expression)
        now = self._utc_now()
        return self.repository.create_decision(
            DecisionJournalRecord(
                decision_id=str(uuid4()),
                revision=1,
                company_id=company.company_id,
                ticker=value.ticker.strip().upper(),
                company_name=company.legal_name,
                decision_type=value.decision_type,
                state=value.state,
                thesis_snapshot=thesis,
                risk_policy_snapshot=self.portfolio.current_policy(),
                position_intent_snapshot=intent,
                expression_snapshot=expression,
                entry_plan_snapshot=entry_plan,
                rationale=value.rationale.strip(),
                actual_execution=value.actual_execution,
                process_review=ProcessReview(),
                later_outcome=None,
                process_outcome_classification=None,
                option_position_id=value.option_position_id,
                created_at=now,
                updated_at=now,
            )
        )

    def update_decision(self, decision_id: str, value: DecisionJournalUpdate) -> DecisionJournalRecord:
        current = self.repository.decision(decision_id)
        if current is None:
            raise LookupError("Decision journal record was not found.")
        classification = process_outcome_classification(
            value.process_review.process_quality,
            value.later_outcome.outcome if value.later_outcome else None,
        )
        return self.repository.update_decision(
            current,
            state=value.state,
            rationale=value.rationale,
            actual_execution=value.actual_execution,
            process_review=value.process_review,
            later_outcome=value.later_outcome,
            classification=classification,
        )

    def decision(self, decision_id: str) -> DecisionJournalRecord | None:
        return self.repository.decision(decision_id)

    def decisions(self, filters: DecisionJournalFilters, limit: int = 100) -> list[DecisionJournalRecord]:
        return self.repository.list_decisions(filters, limit)

    def decision_revisions(self, decision_id: str) -> list[DecisionJournalRecord]:
        return self.repository.decision_revisions(decision_id)

    def _company(self, ticker: str) -> CompanyIdentity:
        company = self.identities.resolve_ticker(ticker.strip().upper())
        if company is None:
            raise LookupError(f"No canonical company identity exists for ticker {ticker.strip().upper()}.")
        return company

    def _intent(self, intent_id: str, company_id: str) -> PositionIntent:
        intent = self.repository.intent(intent_id)
        if intent is None or intent.company_id != company_id:
            raise LookupError("Position intent was not found for this company.")
        return intent

    @staticmethod
    def _validate_expression_ticker(ticker: str, expression: InstrumentExpression) -> None:
        if expression.option_position and expression.option_position.ticker.strip().upper() != ticker.strip().upper():
            raise ValueError("Option expression ticker must match the Decision Center company.")

    @staticmethod
    def _resolve_amount_percent(
        amount: float | None,
        percent: float | None,
        investable: float | None,
        label: str,
    ) -> tuple[float | None, float | None]:
        resolved_amount = round(amount, 2) if amount is not None else None
        resolved_percent = round(percent, 4) if percent is not None else None
        if investable is not None and investable > 0:
            calculated_amount = investable * percent / 100 if percent is not None else None
            calculated_percent = amount / investable * 100 if amount is not None else None
            if amount is not None and percent is not None and calculated_amount is not None:
                if abs(amount - calculated_amount) > max(1, investable * 0.001):
                    raise ValueError(f"{label.title()} amount and percentage do not reconcile to investable value.")
            resolved_amount = resolved_amount if resolved_amount is not None else round(float(calculated_amount), 2)
            resolved_percent = resolved_percent if resolved_percent is not None else round(float(calculated_percent), 4)
        return resolved_amount, resolved_percent

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
