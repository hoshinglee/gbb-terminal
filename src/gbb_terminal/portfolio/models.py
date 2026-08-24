from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PortfolioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PortfolioContextInput(PortfolioModel):
    investable_value: float = Field(ge=0)
    liquid_cash: float = Field(ge=0)
    base_currency: Literal["USD"] = "USD"

    @model_validator(mode="after")
    def validate_cash(self) -> "PortfolioContextInput":
        if self.liquid_cash > self.investable_value:
            raise ValueError("Liquid cash cannot exceed investable portfolio value.")
        return self


class PortfolioContext(PortfolioContextInput):
    context_id: str
    created_at: datetime
    updated_at: datetime


class PortfolioPositionInput(PortfolioModel):
    ticker: str = Field(min_length=1, max_length=12)
    shares: float
    cost_basis_per_share: float = Field(ge=0)
    manual_market_value: float | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ticker is required.")
        return normalized

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, value: float) -> float:
        if value == 0:
            raise ValueError("Shares must be non-zero.")
        return value


class PortfolioPosition(PortfolioPositionInput):
    position_id: str
    context_id: str
    company_id: str | None = None
    company_name: str | None = None
    identity_status: Literal["resolved", "unresolved"]
    created_at: datetime
    updated_at: datetime


class RiskPolicyInput(PortfolioModel):
    name: str = Field(min_length=1, max_length=120)
    normal_target_position_percent: float = Field(gt=0, le=100)
    max_single_name_exposure_percent: float = Field(gt=0, le=100)
    max_assignment_exposure_percent: float = Field(gt=0, le=100)
    max_short_option_collateral_percent: float = Field(gt=0, le=100)
    min_unencumbered_cash_reserve_percent: float | None = Field(default=None, ge=0, le=100)
    min_unencumbered_cash_reserve_amount: float | None = Field(default=None, ge=0)
    portfolio_stress_loss_ceiling_percent: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_policy(self) -> "RiskPolicyInput":
        if self.normal_target_position_percent > self.max_single_name_exposure_percent:
            raise ValueError("Normal target position cannot exceed maximum single-name exposure.")
        if (
            self.min_unencumbered_cash_reserve_percent is None
            and self.min_unencumbered_cash_reserve_amount is None
        ):
            raise ValueError("Define the minimum cash reserve as a percentage, an amount, or both.")
        return self


class RiskPolicy(RiskPolicyInput):
    policy_id: str
    policy_key: str
    version: int
    supersedes_policy_id: str | None = None
    created_at: datetime


class RiskPolicySnapshot(PortfolioModel):
    snapshot_id: str
    policy_id: str
    policy_key: str
    policy_version: int
    policy: RiskPolicy
    created_at: datetime


class PortfolioBundle(PortfolioModel):
    context: PortfolioContext | None = None
    positions: list[PortfolioPosition] = Field(default_factory=list)
    risk_policy: RiskPolicy | None = None

