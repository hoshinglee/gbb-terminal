from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ENGINE_VERSION = "2.1.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParameterMode(StrEnum):
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    SEARCH = "search"


class ParameterType(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHOICE = "choice"


class ParameterSpec(ContractModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    parameter_type: ParameterType
    unit: str = ""
    default: int | float | bool | str
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: list[str] = Field(default_factory=list)
    adaptive_modes: list[str] = Field(default_factory=list)
    searchable: bool = True

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Parameter minimum cannot exceed its maximum.")
        if self.step is not None and self.step <= 0:
            raise ValueError("Parameter step must be positive.")
        if self.parameter_type == ParameterType.INTEGER and (isinstance(self.default, bool) or int(self.default) != self.default):
            raise ValueError("Integer parameters require an integer default.")
        if self.parameter_type == ParameterType.NUMBER and (isinstance(self.default, bool) or not isinstance(self.default, (int, float))):
            raise ValueError("Number parameters require a numeric default.")
        if self.parameter_type == ParameterType.BOOLEAN and not isinstance(self.default, bool):
            raise ValueError("Boolean parameters require a boolean default.")
        if self.parameter_type == ParameterType.CHOICE and (not self.choices or self.default not in self.choices):
            raise ValueError("Choice parameters require choices containing the default.")
        if isinstance(self.default, (int, float)) and not isinstance(self.default, bool):
            if not math.isfinite(float(self.default)):
                raise ValueError("Parameter defaults must be finite.")
            if self.minimum is not None and self.default < self.minimum:
                raise ValueError("Parameter default cannot be below its minimum.")
            if self.maximum is not None and self.default > self.maximum:
                raise ValueError("Parameter default cannot exceed its maximum.")
        return self


class DataRequirement(ContractModel):
    dataset: str
    fields: list[str]
    point_in_time: bool = False


class ExecutionAssumptions(ContractModel):
    initial_capital: float = Field(default=100_000, gt=0)
    commission_bps: float = Field(default=1.0, ge=0, le=100)
    slippage_bps: float = Field(default=2.0, ge=0, le=100)
    annual_cash_rate: float = Field(default=0.0, ge=-0.1, le=0.25)
    signal_lag_sessions: Literal[1] = 1
    fill_price: Literal["next_open"] = "next_open"

    @property
    def one_way_cost_rate(self) -> float:
        return (self.commission_bps + self.slippage_bps) / 10_000


class ValidationDesign(ContractModel):
    training_fraction: float = Field(default=0.6, ge=0.5, le=0.8)
    final_test_fraction: float = Field(default=0.2, ge=0.1, le=0.35)
    walk_forward_folds: int = Field(default=3, ge=2, le=10)

    @model_validator(mode="after")
    def leave_validation_window(self) -> "ValidationDesign":
        if self.training_fraction + self.final_test_fraction > 0.95:
            raise ValueError("Training and final-test windows must leave at least 5% for validation.")
        return self


class StrategyTemplate(ContractModel):
    template_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    family: str
    version: int = Field(default=2, ge=1)
    name: str
    description: str
    direction: Literal["long", "short"] = "long"
    parameters: list[ParameterSpec]
    required_datasets: list[DataRequirement]
    rule_graph: dict[str, Any]


class StrategyInstance(ContractModel):
    instance_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    template_version: int = Field(default=2, ge=1)
    name: str
    description: str
    parameter_values: dict[str, int | float | bool | str]
    parameter_modes: dict[str, ParameterMode] = Field(default_factory=dict)
    ticker: str | None = None
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    sector_benchmark: str | None = None
    timeframe: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "1y"
    risk: dict[str, float] = Field(default_factory=dict)
    execution: ExecutionAssumptions = Field(default_factory=ExecutionAssumptions)

    @field_validator("ticker", "benchmark", "sector_benchmark", mode="before")
    @classmethod
    def normalize_symbol(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @field_validator("universe", mode="before")
    @classmethod
    def normalize_universe(cls, value: object) -> object:
        if value is None:
            return []
        return list(dict.fromkeys(str(symbol).strip().upper() for symbol in value if str(symbol).strip()))

    @model_validator(mode="after")
    def validate_instance(self) -> Self:
        if not self.benchmark:
            raise ValueError("A benchmark symbol is required.")
        for key, value in self.parameter_values.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Parameter '{key}' must be finite.")
        unknown_modes = set(self.parameter_modes) - set(self.parameter_values)
        if unknown_modes:
            raise ValueError(f"Parameter modes reference unknown values: {', '.join(sorted(unknown_modes))}.")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"instance_id", "name", "description", "parameter_modes"})
        payload["parameter_values"] = dict(sorted(payload["parameter_values"].items()))
        return payload

    def semantic_key(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


class DataSnapshot(ContractModel):
    symbol: str
    start_date: date
    end_date: date
    rows: int = Field(gt=0)
    columns: list[str]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("Snapshot start date cannot follow its end date.")
        if not self.columns:
            raise ValueError("Snapshot columns cannot be empty.")
        object.__setattr__(self, "symbol", self.symbol.upper())
        return self


class ResearchRun(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    strategy: StrategyInstance
    strategy_key: str = ""
    data_snapshot: dict[str, DataSnapshot]
    engine_version: str = ENGINE_VERSION
    validation: ValidationDesign = Field(default_factory=ValidationDesign)
    tested_parameters: list[dict[str, Any]] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    reproducibility_key: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def assign_reproducibility_identity(self) -> Self:
        strategy_key = self.strategy.semantic_key()
        if self.strategy_key and self.strategy_key != strategy_key:
            raise ValueError("Research-run strategy key does not match its canonical strategy payload.")
        for symbol, snapshot in self.data_snapshot.items():
            if symbol.upper() != snapshot.symbol:
                raise ValueError(f"Snapshot key '{symbol}' does not match symbol '{snapshot.symbol}'.")
        payload = {
            "strategyKey": strategy_key,
            "data": {symbol: snapshot.sha256 for symbol, snapshot in sorted(self.data_snapshot.items())},
            "engineVersion": self.engine_version,
            "validation": self.validation.model_dump(mode="json"),
        }
        reproducibility_key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.reproducibility_key and self.reproducibility_key != reproducibility_key:
            raise ValueError("Research-run reproducibility key does not match its canonical inputs.")
        object.__setattr__(self, "strategy_key", strategy_key)
        object.__setattr__(self, "reproducibility_key", reproducibility_key)
        return self
