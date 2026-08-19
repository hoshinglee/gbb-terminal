from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UniverseKey(StrEnum):
    SP500 = "sp500"


class UniverseRefreshStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UniverseItemStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class UniverseRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_snapshot: bool = True
    force: bool = False
    max_companies: int | None = Field(default=None, ge=1, le=600)
    concurrency: int = Field(default=4, ge=1, le=8)
    max_attempts: int = Field(default=2, ge=1, le=3)
    fresh_hours: int = Field(default=24, ge=1, le=720)


class UniverseConstituent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    source_symbol: str
    company_name: str
    sector: str
    sub_industry: str
    cik: str
    date_added: date | None = None
    company_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("symbol", "source_symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("cik", mode="before")
    @classmethod
    def normalize_cik(cls, value: str | int) -> str:
        digits = "".join(character for character in str(value) if character.isdigit())
        if not digits:
            raise ValueError("A universe constituent requires a numeric SEC CIK.")
        return digits.zfill(10)


class UniverseSourceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_key: UniverseKey
    as_of_date: date
    source: str
    source_url: str
    known_at: datetime
    retrieved_at: datetime
    content_hash: str
    constituents: list[UniverseConstituent]
    quality_warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @field_validator("known_at", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Universe source timestamps must include a timezone offset.")
        return value


class UniverseSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    universe_key: UniverseKey
    version: int
    as_of_date: date
    source: str
    source_url: str
    known_at: datetime
    retrieved_at: datetime
    content_hash: str
    constituent_count: int
    constituents: list[UniverseConstituent]
    quality_warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class UniverseRefreshItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    refresh_id: str
    symbol: str
    company_id: str | None = None
    status: UniverseItemStatus
    stage: str
    attempt_count: int = 0
    market_cap: float | None = None
    daily_change_percent: float | None = None
    price_observed_at: datetime | None = None
    price_status: str | None = None
    financial_metric_count: int = 0
    valuation_point_count: int = 0
    earnings_event_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime


class UniverseRefreshSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_id: str
    universe_key: UniverseKey
    snapshot_id: str
    status: UniverseRefreshStatus
    profile: str = "company_research"
    total_count: int
    completed_count: int
    partial_count: int
    skipped_count: int
    failed_count: int
    cancelled_count: int
    items: list[UniverseRefreshItem]
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None


class UniverseCompanyCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_key: UniverseKey
    snapshot_id: str
    symbol: str
    company_id: str | None = None
    company_name: str
    sector: str
    sub_industry: str
    status: UniverseItemStatus
    price: float | None = None
    daily_change_percent: float | None = None
    market_cap: float | None = None
    market_cap_source: str = "unavailable_equal_area_fallback"
    observation_timestamp: datetime | None = None
    known_at: datetime | None = None
    retrieved_at: datetime
    financial_metric_count: int = 0
    valuation_point_count: int = 0
    earnings_event_count: int = 0
    quality_warnings: list[str] = Field(default_factory=list)
    last_success_at: datetime | None = None


class UniverseStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_key: UniverseKey
    snapshot: UniverseSnapshot | None = None
    latest_refresh: UniverseRefreshSummary | None = None
    cached_count: int = 0
    completed_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    unavailable_count: int = 0
    sector_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SectorConstituentResearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    company_name: str
    sector: str
    sub_industry: str
    company_id: str | None = None
    price: float | None = None
    daily_change_percent: float | None = None
    market_cap: float | None = None
    market_cap_source: str
    data_status: str
    observation_timestamp: datetime | None = None
    known_at: datetime | None = None
    quality_warnings: list[str] = Field(default_factory=list)


class SectorConstituentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    universe_key: UniverseKey
    snapshot_id: str
    sector_symbol: str
    sector_name: str
    constituent_count: int
    available_count: int
    constituents: list[SectorConstituentResearch]
    gainers: list[SectorConstituentResearch]
    losers: list[SectorConstituentResearch]
    unavailable: list[SectorConstituentResearch]
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)
