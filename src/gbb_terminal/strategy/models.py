from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ParameterMode(StrEnum):
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    SEARCH = "search"


class ParameterType(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHOICE = "choice"


class ParameterSpec(BaseModel):
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


class DataRequirement(BaseModel):
    dataset: str
    fields: list[str]
    point_in_time: bool = False


class ExecutionAssumptions(BaseModel):
    initial_capital: float = Field(default=100_000, gt=0)
    commission_bps: float = Field(default=1.0, ge=0, le=100)
    slippage_bps: float = Field(default=2.0, ge=0, le=100)
    annual_cash_rate: float = Field(default=0.0, ge=-0.1, le=0.25)

    @property
    def one_way_cost_rate(self) -> float:
        return (self.commission_bps + self.slippage_bps) / 10_000


class ValidationDesign(BaseModel):
    training_fraction: float = Field(default=0.7, ge=0.5, le=0.85)
    final_test_fraction: float = Field(default=0.2, ge=0.1, le=0.35)
    walk_forward_folds: int = Field(default=3, ge=2, le=10)

    @model_validator(mode="after")
    def leave_validation_window(self) -> "ValidationDesign":
        if self.training_fraction + self.final_test_fraction > 0.95:
            raise ValueError("Training and final-test windows must leave at least 5% for validation.")
        return self


class StrategyTemplate(BaseModel):
    template_id: str
    family: str
    version: int = Field(default=2, ge=1)
    name: str
    description: str
    direction: Literal["long", "short"] = "long"
    parameters: list[ParameterSpec]
    required_datasets: list[DataRequirement]
    rule_graph: dict[str, Any]


class StrategyInstance(BaseModel):
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
    timeframe: str = "1y"
    risk: dict[str, float] = Field(default_factory=dict)
    execution: ExecutionAssumptions = Field(default_factory=ExecutionAssumptions)

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"instance_id"})
        payload["parameter_modes"] = {key: value for key, value in sorted(payload["parameter_modes"].items())}
        payload["parameter_values"] = dict(sorted(payload["parameter_values"].items()))
        return payload

    def semantic_key(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


class ResearchRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    strategy: StrategyInstance
    data_snapshot: dict[str, str]
    engine_version: str = "2.0"
    validation: ValidationDesign = Field(default_factory=ValidationDesign)
    tested_parameters: list[dict[str, Any]] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

