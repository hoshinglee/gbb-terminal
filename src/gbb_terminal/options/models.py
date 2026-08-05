from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class PositionKind(StrEnum):
    CUSTOM = "custom"
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    SHORT_CALL = "short_call"
    SHORT_PUT = "short_put"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"


class LifecycleEventType(StrEnum):
    HOLD = "hold"
    CLOSE = "close"
    PARTIAL_CLOSE = "partial_close"
    ROLL_STRIKE = "roll_strike"
    ROLL_EXPIRY = "roll_expiry"
    EXERCISE = "exercise"
    EXPIRE = "expire"
    EARLY_ASSIGNMENT = "early_assignment"
    EXPIRY_ASSIGNMENT = "expiry_assignment"


class OptionLeg(BaseModel):
    leg_id: str = Field(default_factory=lambda: str(uuid4()))
    option_type: OptionType
    side: PositionSide
    strike: float = Field(gt=0)
    expiration: date
    premium: float = Field(ge=0)
    quantity: int = Field(default=1, gt=0, le=1000)
    implied_volatility: float = Field(default=0.25, gt=0, le=5)
    multiplier: int = Field(default=100, gt=0)
    contract_symbol: str | None = None


class OptionSimulationRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    underlying_price: float = Field(gt=0)
    position_kind: PositionKind = PositionKind.CUSTOM
    legs: list[OptionLeg] = Field(min_length=1, max_length=4)
    shares: int = Field(default=0, ge=0)
    share_cost_basis: float | None = Field(default=None, gt=0)
    interest_rate: float = Field(default=0.04, ge=-0.05, le=0.5)
    dividend_yield: float = Field(default=0.0, ge=0, le=0.5)
    paths: int = Field(default=200, ge=50, le=2000)
    seed: int = 42

    @model_validator(mode="after")
    def covered_positions_have_collateral(self) -> "OptionSimulationRequest":
        contracts = sum(leg.quantity for leg in self.legs if leg.side == PositionSide.SHORT)
        if self.position_kind == PositionKind.COVERED_CALL and self.shares < contracts * 100:
            raise ValueError("A covered call requires 100 shares for every short call contract.")
        return self


class OptionPositionCreate(OptionSimulationRequest):
    name: str = Field(min_length=3, max_length=100)


class OptionLifecycleEvent(BaseModel):
    event_type: LifecycleEventType
    event_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    underlying_price: float = Field(gt=0)
    option_marks: dict[str, float] = Field(default_factory=dict)
    quantity: int | None = Field(default=None, gt=0)
    leg_id: str | None = None
    new_strike: float | None = Field(default=None, gt=0)
    new_expiration: date | None = None
    new_premium: float | None = Field(default=None, ge=0)
    note: str = Field(default="", max_length=500)


class PositionLedgerState(BaseModel):
    position_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    ticker: str
    position_kind: PositionKind
    status: Literal["open", "closed", "expired", "assigned", "exercised"] = "open"
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    underlying_price: float
    cash: float = 0.0
    shares: int = 0
    share_cost_basis: float = 0.0
    realized_pnl: float = 0.0
    collateral: float = 0.0
    legs: list[OptionLeg]
    closed_quantities: dict[str, int] = Field(default_factory=dict)

