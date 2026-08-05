from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...strategy.models import StrategyInstance, ValidationDesign


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrategyProposalV2Request(APIModel):
    instruction: str = Field(min_length=8, max_length=1000)


class ResearchRunRequest(APIModel):
    strategy: StrategyInstance
    validation: ValidationDesign = Field(default_factory=ValidationDesign)


class ParameterSearchRequest(APIModel):
    strategy: StrategyInstance
    ranges: dict[str, list[int | float]]
    validation: ValidationDesign = Field(default_factory=ValidationDesign)
    max_trials: int = Field(default=60, ge=2, le=200)


class StrategyCreateRequest(APIModel):
    strategy: StrategyInstance
    original_instruction: str = Field(default="", max_length=1000)


class JobResponse(APIModel):
    job_id: str
    status: str
    progress: float
    result: dict[str, Any] | None = None
