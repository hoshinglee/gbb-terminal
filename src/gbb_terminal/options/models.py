from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal
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
    CONVERSION = "conversion"


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
    BUY_SHARES = "buy_shares"
    SELL_SHARES = "sell_shares"
    ADD_LEG = "add_leg"


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
    premium_source: Literal["manual", "ask", "bid", "last", "mid"] = "manual"


class OptionSimulationRequest(BaseModel):
    run_name: str | None = Field(default=None, min_length=3, max_length=100)
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
    data_provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def covered_positions_have_collateral(self) -> "OptionSimulationRequest":
        contracts = sum(leg.quantity for leg in self.legs if leg.side == PositionSide.SHORT)
        if self.position_kind == PositionKind.COVERED_CALL and self.shares < contracts * 100:
            raise ValueError("A covered call requires 100 shares for every short call contract.")
        expected_legs = {
            PositionKind.LONG_CALL: [(OptionType.CALL, PositionSide.LONG)],
            PositionKind.LONG_PUT: [(OptionType.PUT, PositionSide.LONG)],
            PositionKind.SHORT_CALL: [(OptionType.CALL, PositionSide.SHORT)],
            PositionKind.SHORT_PUT: [(OptionType.PUT, PositionSide.SHORT)],
            PositionKind.COVERED_CALL: [(OptionType.CALL, PositionSide.SHORT)],
            PositionKind.CASH_SECURED_PUT: [(OptionType.PUT, PositionSide.SHORT)],
            PositionKind.BULL_CALL_SPREAD: [(OptionType.CALL, PositionSide.LONG), (OptionType.CALL, PositionSide.SHORT)],
            PositionKind.BEAR_CALL_SPREAD: [(OptionType.CALL, PositionSide.SHORT), (OptionType.CALL, PositionSide.LONG)],
            PositionKind.BULL_PUT_SPREAD: [(OptionType.PUT, PositionSide.SHORT), (OptionType.PUT, PositionSide.LONG)],
            PositionKind.BEAR_PUT_SPREAD: [(OptionType.PUT, PositionSide.LONG), (OptionType.PUT, PositionSide.SHORT)],
            PositionKind.CONVERSION: [(OptionType.PUT, PositionSide.LONG), (OptionType.CALL, PositionSide.SHORT)],
        }
        expected = expected_legs.get(self.position_kind)
        actual = [(leg.option_type, leg.side) for leg in self.legs]
        if expected is not None and actual != expected:
            raise ValueError(f"{self.position_kind.replace('_', ' ').title()} requires its declared option-leg roles in order.")
        matching_leg_recipes = {
            PositionKind.BULL_CALL_SPREAD,
            PositionKind.BEAR_CALL_SPREAD,
            PositionKind.BULL_PUT_SPREAD,
            PositionKind.BEAR_PUT_SPREAD,
            PositionKind.CONVERSION,
        }
        if self.position_kind in matching_leg_recipes and (len({leg.expiration for leg in self.legs}) != 1 or len({leg.quantity for leg in self.legs}) != 1):
            raise ValueError("This recipe requires matching expirations and quantities across every option leg.")
        if self.position_kind == PositionKind.BULL_CALL_SPREAD and not self.legs[0].strike < self.legs[1].strike:
            raise ValueError("A bull call spread requires the long-call strike below the short-call strike.")
        if self.position_kind == PositionKind.BEAR_CALL_SPREAD and not self.legs[0].strike < self.legs[1].strike:
            raise ValueError("A bear call spread requires the short-call strike below the long-call strike.")
        if self.position_kind == PositionKind.BULL_PUT_SPREAD and not self.legs[0].strike > self.legs[1].strike:
            raise ValueError("A bull put spread requires the short-put strike above the long-put strike.")
        if self.position_kind == PositionKind.BEAR_PUT_SPREAD and not self.legs[0].strike > self.legs[1].strike:
            raise ValueError("A bear put spread requires the long-put strike above the short-put strike.")
        if self.position_kind == PositionKind.CONVERSION:
            quantity = self.legs[0].quantity
            if self.shares != quantity * self.legs[0].multiplier:
                raise ValueError("A conversion requires exactly 100 shares for every put/call contract pair.")
            if len({leg.strike for leg in self.legs}) != 1:
                raise ValueError("A conversion requires the put and call to use the same strike.")
        return self


class OptionPositionCreate(OptionSimulationRequest):
    name: str = Field(min_length=3, max_length=100)
    research_run_id: str | None = None


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
    new_leg: OptionLeg | None = None
    note: str = Field(default="", max_length=500)


class PositionLedgerState(BaseModel):
    position_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    ticker: str
    position_kind: PositionKind
    research_run_id: str | None = None
    current_structure: str = ""
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
