from __future__ import annotations

from ..intelligence.identity import normalize_ticker
from ..intelligence.service import CompanyIdentityService
from .models import (
    PortfolioBundle,
    PortfolioContext,
    PortfolioContextInput,
    PortfolioPosition,
    PortfolioPositionInput,
    RiskPolicy,
    RiskPolicyInput,
    RiskPolicySnapshot,
)
from .repository import PortfolioRepository


class PortfolioService:
    def __init__(self, repository: PortfolioRepository, identities: CompanyIdentityService) -> None:
        self.repository = repository
        self.identities = identities

    def bundle(self) -> PortfolioBundle:
        return PortfolioBundle(
            context=self.repository.get_context(),
            positions=self.repository.list_positions(),
            risk_policy=self.repository.current_policy(),
        )

    def save_context(self, value: PortfolioContextInput) -> PortfolioContext:
        return self.repository.save_context(value)

    def create_position(self, value: PortfolioPositionInput) -> PortfolioPosition:
        normalized = value.model_copy(update={"ticker": normalize_ticker(value.ticker)})
        company = self.identities.resolve_ticker(normalized.ticker)
        return self.repository.save_position(
            normalized,
            company_id=company.company_id if company else None,
        )

    def update_position(self, position_id: str, value: PortfolioPositionInput) -> PortfolioPosition:
        normalized = value.model_copy(update={"ticker": normalize_ticker(value.ticker)})
        company = self.identities.resolve_ticker(normalized.ticker)
        return self.repository.save_position(
            normalized,
            company_id=company.company_id if company else None,
            position_id=position_id,
        )

    def delete_position(self, position_id: str) -> bool:
        return self.repository.delete_position(position_id)

    def current_policy(self) -> RiskPolicy | None:
        return self.repository.current_policy()

    def save_policy(self, value: RiskPolicyInput) -> RiskPolicy:
        return self.repository.save_policy(value)

    def snapshot_policy(self) -> RiskPolicySnapshot:
        return self.repository.snapshot_current_policy()

    def policy_snapshot(self, snapshot_id: str) -> RiskPolicySnapshot | None:
        return self.repository.get_policy_snapshot(snapshot_id)
