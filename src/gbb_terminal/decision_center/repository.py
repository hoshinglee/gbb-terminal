from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb

from .models import (
    DecisionJournalFilters,
    DecisionJournalRecord,
    EntryPlan,
    EntryPlanInput,
    EntryTranche,
    LaterOutcome,
    PositionIntent,
    ProcessReview,
    ThesisCard,
    ThesisCardInput,
    ThesisEvidenceReference,
    ThesisSnapshot,
)


class DecisionCenterRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def current_thesis(self, company_id: str) -> ThesisCard | None:
        row = self.connection.execute(
            """SELECT payload FROM decision_theses
               WHERE company_id = ? ORDER BY version DESC LIMIT 1""",
            [company_id],
        ).fetchone()
        return ThesisCard.model_validate(self._json(row[0])) if row else None

    def thesis(self, thesis_id: str) -> ThesisCard | None:
        row = self.connection.execute(
            "SELECT payload FROM decision_theses WHERE thesis_id = ?",
            [thesis_id],
        ).fetchone()
        return ThesisCard.model_validate(self._json(row[0])) if row else None

    def save_thesis(
        self,
        company_id: str,
        ticker: str,
        company_name: str,
        value: ThesisCardInput,
        evidence_references: list[ThesisEvidenceReference],
    ) -> ThesisCard:
        current = self.current_thesis(company_id)
        thesis = ThesisCard(
            thesis_id=str(uuid4()),
            thesis_key=f"company:{company_id}",
            company_id=company_id,
            ticker=ticker,
            company_name=company_name,
            version=(current.version + 1) if current else 1,
            status=value.status,
            evidence_strength=value.evidence_strength,
            moat_assessment=value.moat_assessment,
            major_risks=self._clean_list(value.major_risks),
            catalysts=self._clean_list(value.catalysts),
            invalidation_criteria=self._clean_list(value.invalidation_criteria),
            rationale=value.rationale.strip(),
            evidence_references=evidence_references,
            supersedes_thesis_id=current.thesis_id if current else None,
            created_at=self._utc_now(),
        )
        self.connection.execute(
            """INSERT INTO decision_theses
               (thesis_id, thesis_key, company_id, ticker, version, status, payload, supersedes_thesis_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                thesis.thesis_id,
                thesis.thesis_key,
                thesis.company_id,
                thesis.ticker,
                thesis.version,
                thesis.status.value,
                self._dump(thesis),
                thesis.supersedes_thesis_id,
                thesis.created_at,
            ],
        )
        return thesis

    def snapshot_thesis(self, thesis: ThesisCard) -> ThesisSnapshot:
        snapshot = ThesisSnapshot(
            snapshot_id=str(uuid4()),
            thesis_id=thesis.thesis_id,
            thesis_version=thesis.version,
            thesis=thesis,
            created_at=self._utc_now(),
        )
        self.connection.execute(
            """INSERT INTO decision_thesis_snapshots
               (snapshot_id, thesis_id, company_id, thesis_version, payload, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                snapshot.snapshot_id,
                thesis.thesis_id,
                thesis.company_id,
                thesis.version,
                self._dump(snapshot),
                snapshot.created_at,
            ],
        )
        return snapshot

    def thesis_snapshot(self, snapshot_id: str) -> ThesisSnapshot | None:
        row = self.connection.execute(
            "SELECT payload FROM decision_thesis_snapshots WHERE snapshot_id = ?",
            [snapshot_id],
        ).fetchone()
        return ThesisSnapshot.model_validate(self._json(row[0])) if row else None

    def current_intent(self, company_id: str) -> PositionIntent | None:
        row = self.connection.execute(
            """SELECT payload FROM decision_position_intents
               WHERE company_id = ? ORDER BY version DESC LIMIT 1""",
            [company_id],
        ).fetchone()
        return PositionIntent.model_validate(self._json(row[0])) if row else None

    def intent(self, intent_id: str) -> PositionIntent | None:
        row = self.connection.execute(
            "SELECT payload FROM decision_position_intents WHERE intent_id = ?",
            [intent_id],
        ).fetchone()
        return PositionIntent.model_validate(self._json(row[0])) if row else None

    def save_intent(self, intent: PositionIntent) -> PositionIntent:
        self.connection.execute(
            """INSERT INTO decision_position_intents
               (intent_id, intent_key, company_id, ticker, version, payload, supersedes_intent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                intent.intent_id,
                intent.intent_key,
                intent.company_id,
                intent.ticker,
                intent.version,
                self._dump(intent),
                intent.supersedes_intent_id,
                intent.created_at,
            ],
        )
        return intent

    def entry_plan(self, entry_plan_id: str) -> EntryPlan | None:
        row = self.connection.execute(
            "SELECT payload FROM decision_entry_plans WHERE entry_plan_id = ?",
            [entry_plan_id],
        ).fetchone()
        return EntryPlan.model_validate(self._json(row[0])) if row else None

    def list_entry_plans(self, company_id: str) -> list[EntryPlan]:
        rows = self.connection.execute(
            """SELECT payload FROM decision_entry_plans
               WHERE company_id = ? ORDER BY plan_key, version DESC""",
            [company_id],
        ).fetchall()
        plans: list[EntryPlan] = []
        seen: set[str] = set()
        for row in rows:
            plan = EntryPlan.model_validate(self._json(row[0]))
            if plan.plan_key not in seen:
                seen.add(plan.plan_key)
                plans.append(plan)
        return sorted(plans, key=lambda plan: plan.created_at, reverse=True)

    def save_entry_plan(
        self,
        company_id: str,
        ticker: str,
        company_name: str,
        value: EntryPlanInput,
        tranches: list[EntryTranche],
        target_allocation_amount: float,
        *,
        prior: EntryPlan | None = None,
    ) -> EntryPlan:
        allocated = round(sum(tranche.resolved_allocation_amount for tranche in tranches), 2)
        plan = EntryPlan(
            entry_plan_id=str(uuid4()),
            plan_key=prior.plan_key if prior else str(uuid4()),
            company_id=company_id,
            ticker=ticker,
            company_name=company_name,
            version=(prior.version + 1) if prior else 1,
            position_intent_id=value.position_intent_id,
            expression=value.expression,
            execution_mode=value.execution_mode,
            escape_plan=value.escape_plan,
            target_allocation_amount=round(target_allocation_amount, 2),
            allocated_amount=allocated,
            unallocated_reserve=round(max(target_allocation_amount - allocated, 0), 2),
            tranches=tranches,
            notes=value.notes.strip(),
            supersedes_entry_plan_id=prior.entry_plan_id if prior else None,
            created_at=self._utc_now(),
        )
        self.connection.execute(
            """INSERT INTO decision_entry_plans
               (entry_plan_id, plan_key, company_id, ticker, version, payload, supersedes_entry_plan_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                plan.entry_plan_id,
                plan.plan_key,
                plan.company_id,
                plan.ticker,
                plan.version,
                self._dump(plan),
                plan.supersedes_entry_plan_id,
                plan.created_at,
            ],
        )
        return plan

    def create_decision(self, record: DecisionJournalRecord) -> DecisionJournalRecord:
        self.connection.execute(
            """INSERT INTO decision_journal
               (decision_id, company_id, ticker, decision_type, state, review_status, payload, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                record.decision_id,
                record.company_id,
                record.ticker,
                record.decision_type,
                record.state,
                self._review_status(record.process_review),
                self._dump(record),
                record.created_at,
                record.updated_at,
            ],
        )
        self._append_decision_revision(record)
        return record

    def decision(self, decision_id: str) -> DecisionJournalRecord | None:
        row = self.connection.execute(
            "SELECT payload FROM decision_journal WHERE decision_id = ?",
            [decision_id],
        ).fetchone()
        return DecisionJournalRecord.model_validate(self._json(row[0])) if row else None

    def update_decision(
        self,
        current: DecisionJournalRecord,
        *,
        state: str,
        rationale: str,
        actual_execution: dict,
        process_review: ProcessReview,
        later_outcome: LaterOutcome | None,
        classification: str | None,
    ) -> DecisionJournalRecord:
        updated = current.model_copy(
            update={
                "revision": current.revision + 1,
                "state": state,
                "rationale": rationale.strip(),
                "actual_execution": actual_execution,
                "process_review": process_review,
                "later_outcome": later_outcome,
                "process_outcome_classification": classification,
                "updated_at": self._utc_now(),
            }
        )
        self.connection.execute(
            """UPDATE decision_journal
               SET state = ?, review_status = ?, payload = ?, updated_at = ?
               WHERE decision_id = ?""",
            [
                updated.state,
                self._review_status(updated.process_review),
                self._dump(updated),
                updated.updated_at,
                updated.decision_id,
            ],
        )
        self._append_decision_revision(updated)
        return updated

    def list_decisions(self, filters: DecisionJournalFilters, limit: int = 100) -> list[DecisionJournalRecord]:
        conditions: list[str] = []
        parameters: list[object] = []
        if filters.ticker:
            conditions.append("ticker = ?")
            parameters.append(filters.ticker.strip().upper())
        if filters.state:
            conditions.append("state = ?")
            parameters.append(filters.state)
        if filters.decision_type:
            conditions.append("decision_type = ?")
            parameters.append(filters.decision_type)
        if filters.start_date:
            conditions.append("created_at >= ?")
            parameters.append(datetime.combine(filters.start_date, datetime.min.time()))
        if filters.end_date:
            conditions.append("created_at < ?")
            parameters.append(datetime.combine(filters.end_date, datetime.max.time()))
        if filters.review_status:
            conditions.append("review_status = ?")
            parameters.append(filters.review_status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        rows = self.connection.execute(
            f"SELECT payload FROM decision_journal {where} ORDER BY updated_at DESC LIMIT ?",
            parameters,
        ).fetchall()
        return [DecisionJournalRecord.model_validate(self._json(row[0])) for row in rows]

    def decision_revisions(self, decision_id: str) -> list[DecisionJournalRecord]:
        rows = self.connection.execute(
            """SELECT payload FROM decision_journal_revisions
               WHERE decision_id = ? ORDER BY revision""",
            [decision_id],
        ).fetchall()
        return [DecisionJournalRecord.model_validate(self._json(row[0])) for row in rows]

    def _append_decision_revision(self, record: DecisionJournalRecord) -> None:
        self.connection.execute(
            """INSERT INTO decision_journal_revisions
               (revision_id, decision_id, revision, payload, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [str(uuid4()), record.decision_id, record.revision, self._dump(record), record.updated_at],
        )

    @staticmethod
    def _review_status(review: ProcessReview) -> str:
        return "unreviewed" if review.process_quality == "unreviewed" else "reviewed"

    @staticmethod
    def _clean_list(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    @staticmethod
    def _dump(value: object) -> str:
        return json.dumps(value.model_dump(mode="json"))  # type: ignore[attr-defined]

    @staticmethod
    def _json(value: object) -> object:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
