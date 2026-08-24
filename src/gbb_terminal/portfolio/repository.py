from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb

from .models import (
    PortfolioContext,
    PortfolioContextInput,
    PortfolioPosition,
    PortfolioPositionInput,
    RiskPolicy,
    RiskPolicyInput,
    RiskPolicySnapshot,
)


PERSONAL_CONTEXT_ID = "personal"
PERSONAL_POLICY_KEY = "personal-default"


class PortfolioRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def get_context(self) -> PortfolioContext | None:
        row = self.connection.execute(
            """SELECT context_id, investable_value, liquid_cash, base_currency, created_at, updated_at
               FROM portfolio_contexts WHERE context_id = ?""",
            [PERSONAL_CONTEXT_ID],
        ).fetchone()
        return self._context(row) if row else None

    def save_context(self, value: PortfolioContextInput) -> PortfolioContext:
        now = self._utc_now()
        existing = self.connection.execute(
            "SELECT created_at FROM portfolio_contexts WHERE context_id = ?",
            [PERSONAL_CONTEXT_ID],
        ).fetchone()
        created_at = existing[0] if existing else now
        self.connection.execute(
            """INSERT OR REPLACE INTO portfolio_contexts
               (context_id, owner_id, investable_value, liquid_cash, base_currency, created_at, updated_at)
               VALUES (?, NULL, ?, ?, ?, ?, ?)""",
            [
                PERSONAL_CONTEXT_ID,
                value.investable_value,
                value.liquid_cash,
                value.base_currency,
                created_at,
                now,
            ],
        )
        return self.get_context()  # type: ignore[return-value]

    def list_positions(self) -> list[PortfolioPosition]:
        rows = self.connection.execute(
            """SELECT p.position_id, p.context_id, p.company_id, c.legal_name, p.ticker, p.shares,
                      p.cost_basis_per_share, p.manual_market_value, p.notes, p.created_at, p.updated_at
               FROM portfolio_positions p
               LEFT JOIN companies c ON c.company_id = p.company_id
               WHERE p.context_id = ?
               ORDER BY p.ticker""",
            [PERSONAL_CONTEXT_ID],
        ).fetchall()
        return [self._position(row) for row in rows]

    def get_position(self, position_id: str) -> PortfolioPosition | None:
        row = self.connection.execute(
            """SELECT p.position_id, p.context_id, p.company_id, c.legal_name, p.ticker, p.shares,
                      p.cost_basis_per_share, p.manual_market_value, p.notes, p.created_at, p.updated_at
               FROM portfolio_positions p
               LEFT JOIN companies c ON c.company_id = p.company_id
               WHERE p.position_id = ? AND p.context_id = ?""",
            [position_id, PERSONAL_CONTEXT_ID],
        ).fetchone()
        return self._position(row) if row else None

    def save_position(
        self,
        value: PortfolioPositionInput,
        *,
        company_id: str | None,
        position_id: str | None = None,
    ) -> PortfolioPosition:
        if self.get_context() is None:
            raise ValueError("Define investable portfolio value and liquid cash before adding holdings.")
        now = self._utc_now()
        existing = None
        if position_id:
            existing = self.connection.execute(
                "SELECT created_at FROM portfolio_positions WHERE position_id = ? AND context_id = ?",
                [position_id, PERSONAL_CONTEXT_ID],
            ).fetchone()
            if existing is None:
                raise LookupError("Portfolio position was not found.")
        resolved_id = position_id or str(uuid4())
        conflict = self.connection.execute(
            """SELECT position_id FROM portfolio_positions
               WHERE context_id = ? AND ticker = ? AND position_id <> ?""",
            [PERSONAL_CONTEXT_ID, value.ticker, resolved_id],
        ).fetchone()
        if conflict:
            raise ValueError(f"A portfolio position for {value.ticker} already exists.")
        created_at = existing[0] if existing else now
        if existing:
            self.connection.execute(
                """UPDATE portfolio_positions
                   SET company_id = ?, ticker = ?, shares = ?, cost_basis_per_share = ?,
                       manual_market_value = ?, notes = ?, updated_at = ?
                   WHERE position_id = ? AND context_id = ?""",
                [
                    company_id,
                    value.ticker,
                    value.shares,
                    value.cost_basis_per_share,
                    value.manual_market_value,
                    value.notes,
                    now,
                    resolved_id,
                    PERSONAL_CONTEXT_ID,
                ],
            )
        else:
            self.connection.execute(
                """INSERT INTO portfolio_positions
                   (position_id, context_id, company_id, ticker, shares, cost_basis_per_share,
                    manual_market_value, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    resolved_id,
                    PERSONAL_CONTEXT_ID,
                    company_id,
                    value.ticker,
                    value.shares,
                    value.cost_basis_per_share,
                    value.manual_market_value,
                    value.notes,
                    created_at,
                    now,
                ],
            )
        return self.get_position(resolved_id)  # type: ignore[return-value]

    def delete_position(self, position_id: str) -> bool:
        exists = self.get_position(position_id)
        if exists is None:
            return False
        self.connection.execute(
            "DELETE FROM portfolio_positions WHERE position_id = ? AND context_id = ?",
            [position_id, PERSONAL_CONTEXT_ID],
        )
        return True

    def current_policy(self) -> RiskPolicy | None:
        row = self.connection.execute(
            """SELECT policy_id, policy_key, version, name, normal_target_position_percent,
                      max_single_name_exposure_percent, max_assignment_exposure_percent,
                      max_short_option_collateral_percent, min_unencumbered_cash_reserve_percent,
                      min_unencumbered_cash_reserve_amount, portfolio_stress_loss_ceiling_percent,
                      supersedes_policy_id, created_at
               FROM risk_policies WHERE policy_key = ? ORDER BY version DESC LIMIT 1""",
            [PERSONAL_POLICY_KEY],
        ).fetchone()
        return self._policy(row) if row else None

    def save_policy(self, value: RiskPolicyInput) -> RiskPolicy:
        current = self.current_policy()
        policy_id = str(uuid4())
        version = current.version + 1 if current else 1
        now = self._utc_now()
        self.connection.execute(
            """INSERT INTO risk_policies
               (policy_id, policy_key, version, name, normal_target_position_percent,
                max_single_name_exposure_percent, max_assignment_exposure_percent,
                max_short_option_collateral_percent, min_unencumbered_cash_reserve_percent,
                min_unencumbered_cash_reserve_amount, portfolio_stress_loss_ceiling_percent,
                supersedes_policy_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                policy_id,
                PERSONAL_POLICY_KEY,
                version,
                value.name,
                value.normal_target_position_percent,
                value.max_single_name_exposure_percent,
                value.max_assignment_exposure_percent,
                value.max_short_option_collateral_percent,
                value.min_unencumbered_cash_reserve_percent,
                value.min_unencumbered_cash_reserve_amount,
                value.portfolio_stress_loss_ceiling_percent,
                current.policy_id if current else None,
                now,
            ],
        )
        return self.current_policy()  # type: ignore[return-value]

    def snapshot_current_policy(self) -> RiskPolicySnapshot:
        policy = self.current_policy()
        if policy is None:
            raise LookupError("Create a risk policy before taking a snapshot.")
        snapshot_id = str(uuid4())
        now = self._utc_now()
        self.connection.execute(
            """INSERT INTO risk_policy_snapshots
               (snapshot_id, policy_id, policy_key, policy_version, policy, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                snapshot_id,
                policy.policy_id,
                policy.policy_key,
                policy.version,
                json.dumps(policy.model_dump(mode="json")),
                now,
            ],
        )
        return RiskPolicySnapshot(
            snapshot_id=snapshot_id,
            policy_id=policy.policy_id,
            policy_key=policy.policy_key,
            policy_version=policy.version,
            policy=policy,
            created_at=now,
        )

    def get_policy_snapshot(self, snapshot_id: str) -> RiskPolicySnapshot | None:
        row = self.connection.execute(
            """SELECT snapshot_id, policy_id, policy_key, policy_version, policy, created_at
               FROM risk_policy_snapshots WHERE snapshot_id = ?""",
            [snapshot_id],
        ).fetchone()
        if row is None:
            return None
        return RiskPolicySnapshot(
            snapshot_id=row[0],
            policy_id=row[1],
            policy_key=row[2],
            policy_version=row[3],
            policy=RiskPolicy.model_validate(json.loads(row[4])),
            created_at=row[5],
        )

    @staticmethod
    def _context(row: tuple) -> PortfolioContext:
        return PortfolioContext(
            context_id=row[0],
            investable_value=row[1],
            liquid_cash=row[2],
            base_currency=row[3],
            created_at=row[4],
            updated_at=row[5],
        )

    @staticmethod
    def _position(row: tuple) -> PortfolioPosition:
        return PortfolioPosition(
            position_id=row[0],
            context_id=row[1],
            company_id=row[2],
            company_name=row[3],
            ticker=row[4],
            shares=row[5],
            cost_basis_per_share=row[6],
            manual_market_value=row[7],
            notes=row[8] or "",
            identity_status="resolved" if row[2] else "unresolved",
            created_at=row[9],
            updated_at=row[10],
        )

    @staticmethod
    def _policy(row: tuple) -> RiskPolicy:
        return RiskPolicy(
            policy_id=row[0],
            policy_key=row[1],
            version=row[2],
            name=row[3],
            normal_target_position_percent=row[4],
            max_single_name_exposure_percent=row[5],
            max_assignment_exposure_percent=row[6],
            max_short_option_collateral_percent=row[7],
            min_unencumbered_cash_reserve_percent=row[8],
            min_unencumbered_cash_reserve_amount=row[9],
            portfolio_stress_loss_ceiling_percent=row[10],
            supersedes_policy_id=row[11],
            created_at=row[12],
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
