from datetime import date, datetime, timedelta, timezone

from gbb_terminal.decision_center.models import (
    DecisionJournalCreate,
    DecisionJournalFilters,
    DecisionJournalUpdate,
    EntryPlanInput,
    EntryTrancheInput,
    InstrumentExpression,
    LaterOutcome,
    PositionIntentInput,
    ProcessReview,
    ThesisCardInput,
    ThesisEvidenceLinkInput,
)
from gbb_terminal.decision_center.repository import DecisionCenterRepository
from gbb_terminal.decision_center.service import DecisionCenterService
from gbb_terminal.intelligence.evidence_models import EvidenceDocumentCreate, EvidenceSpanCreate
from gbb_terminal.intelligence.evidence_repository import EvidenceRepository
from gbb_terminal.intelligence.models import CompanyProvenance, CompanyRegistration
from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.portfolio.models import PortfolioContextInput, PortfolioPositionInput, RiskPolicyInput
from gbb_terminal.portfolio.repository import PortfolioRepository
from gbb_terminal.portfolio.service import PortfolioService
from gbb_terminal.storage.database import LocalMarketStore


def build_service(path):
    store = LocalMarketStore(path)
    identities = CompanyIdentityRepository(store.connection)
    company = identities.resolve_ticker("NVDA")
    if company is None:
        company = identities.upsert_company(
            CompanyRegistration(
                cik="1045810",
                legal_name="NVIDIA Corporation",
                primary_ticker="NVDA",
                exchange="NASDAQ",
                effective_from=date(1999, 1, 22),
                provenance=CompanyProvenance.local("Decision Fixture"),
            )
        )
    identity_service = CompanyIdentityService(identities, None)
    evidence = EvidenceRepository(store.connection)
    portfolio = PortfolioService(PortfolioRepository(store.connection), identity_service)
    service = DecisionCenterService(
        DecisionCenterRepository(store.connection),
        identity_service,
        evidence,
        portfolio,
    )
    return store, service, evidence, company


def risk_policy(max_position: float = 25) -> RiskPolicyInput:
    return RiskPolicyInput(
        name="Personal Policy",
        normal_target_position_percent=10,
        max_single_name_exposure_percent=max_position,
        max_assignment_exposure_percent=20,
        max_short_option_collateral_percent=25,
        min_unencumbered_cash_reserve_amount=25_000,
        portfolio_stress_loss_ceiling_percent=20,
    )


def test_complete_decision_chain_survives_reopen_with_immutable_snapshots(tmp_path):
    path = tmp_path / "decision-center.duckdb"
    store, service, evidence, company = build_service(path)
    service.portfolio.save_context(PortfolioContextInput(investable_value=200_000, liquid_cash=100_000))
    service.portfolio.create_position(
        PortfolioPositionInput(
            ticker="NVDA",
            shares=25,
            cost_basis_per_share=120,
            manual_market_value=4_000,
            notes="Manual context",
        )
    )
    first_policy = service.portfolio.save_policy(risk_policy())
    now = datetime.now(timezone.utc)
    document = evidence.save_document(
        EvidenceDocumentCreate(
            company_id=company.company_id,
            source="SEC EDGAR",
            dataset="filing_archive",
            document_type="10-k",
            external_id="nvda-10k-2026",
            title="NVIDIA 2026 Form 10-K",
            form="10-K",
            source_url="https://www.sec.gov/example",
            filed_at=now,
            known_at=now,
            retrieved_at=now,
            content_hash="a" * 64,
        )
    )
    span = evidence.save_span(
        EvidenceSpanCreate(
            document_id=document.document_id,
            exact_text="Demand is concentrated in accelerated computing platforms.",
            section="Business",
            extraction_method="manual_fixture",
            extracted_at=now,
        )
    )
    first_thesis = service.save_thesis(
        "NVDA",
        ThesisCardInput(
            status="ready_for_position_planning",
            evidence_strength="strong",
            moat_assessment="moderate",
            major_risks=["Customer concentration"],
            catalysts=["New architecture launch"],
            invalidation_criteria=["Sustained loss of platform demand"],
            rationale="Evidence supports planning, not automatic action.",
            evidence_links=[ThesisEvidenceLinkInput(span_id=span.span_id, interpretation="Demand evidence")],
        ),
    )
    thesis_snapshot = service.snapshot_thesis("NVDA")
    intent = service.save_position_intent(
        "NVDA",
        PositionIntentInput(target_percent=10, maximum_percent=15, current_price=160),
    )
    expression = InstrumentExpression(kind="direct_shares", name="Direct Shares", share_price=160, share_quantity=100)
    plans = []
    for mode in ("patient", "establish_exposure", "catalyst"):
        plans.append(
            service.save_entry_plan(
                "NVDA",
                EntryPlanInput(
                    position_intent_id=intent.intent_id,
                    expression=expression,
                    execution_mode=mode,
                    escape_plan="reassess_thesis" if mode == "catalyst" else "abandon_wait",
                    tranches=[
                        EntryTrancheInput(label="Starter", allocation_percent=30, preferred_entry_price=155, maximum_acceptable_execution_price=160),
                        EntryTrancheInput(label="Confirmation", allocation_percent=40, trigger="Evidence confirms"),
                        EntryTrancheInput(label="Opportunity Reserve", allocation_percent=20, status="available"),
                    ],
                ),
            )
        )
    assert plans[0].unallocated_reserve == 2_000
    assert {plan.execution_mode for plan in plans} == {"patient", "establish_exposure", "catalyst"}

    entered = service.create_decision(
        DecisionJournalCreate(
            ticker="NVDA",
            decision_type="ownership",
            state="entered",
            thesis_id=first_thesis.thesis_id,
            position_intent_id=intent.intent_id,
            expression=expression,
            entry_plan_id=plans[0].entry_plan_id,
            rationale="Entered according to the staged plan.",
        )
    )
    for state in ("partially_entered", "missed", "cancelled", "passed"):
        service.create_decision(
            DecisionJournalCreate(
                ticker="NVDA",
                decision_type="pass" if state == "passed" else "ownership",
                state=state,
                thesis_id=first_thesis.thesis_id,
                position_intent_id=intent.intent_id,
                rationale=f"{state.replace('_', ' ').title()} fixture.",
            )
        )

    service.save_thesis(
        "NVDA",
        ThesisCardInput(
            status="invalidated",
            evidence_strength="limited",
            moat_assessment="limited",
            invalidation_criteria=["Demand evidence invalidated"],
            rationale="Later revision",
        ),
    )
    service.portfolio.save_policy(risk_policy(30))
    closed = service.update_decision(
        entered.decision_id,
        DecisionJournalUpdate(
            state="closed",
            rationale="Closed under the original invalidation rule.",
            process_review=ProcessReview(
                thesis_evidence_sufficient="yes",
                position_inside_risk_budget="yes",
                instrument_fit_intended_exposure="yes",
                execution_followed_plan="yes",
                exit_followed_rule="yes",
                process_quality="good",
            ),
            later_outcome=LaterOutcome(
                as_of=date.today() + timedelta(days=30),
                outcome="unfavorable",
                return_percent=-12,
                description="The later market outcome was unfavorable.",
            ),
        ),
    )
    assert closed.process_outcome_classification == "good_process_unfavorable_outcome"
    assert closed.thesis_snapshot.version == 1
    assert closed.risk_policy_snapshot.version == first_policy.version
    assert thesis_snapshot.thesis.evidence_references[0].exact_text.startswith("Demand is concentrated")
    store.connection.close()

    reopened_store, reopened, _, _ = build_service(path)
    restored = reopened.decision(entered.decision_id)
    assert restored.state == "closed"
    assert restored.thesis_snapshot.version == 1
    assert restored.risk_policy_snapshot.version == 1
    assert len(reopened.decision_revisions(entered.decision_id)) == 2
    assert len(reopened.decisions(DecisionJournalFilters(ticker="NVDA"))) == 5
    assert reopened.decisions(DecisionJournalFilters(state="missed"))[0].state == "missed"
    assert reopened.decisions(DecisionJournalFilters(review_status="reviewed"))[0].decision_id == entered.decision_id
    reopened_store.connection.close()
