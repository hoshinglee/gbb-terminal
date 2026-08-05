from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar


Dataset = TypeVar("Dataset")


@dataclass(frozen=True)
class DataEnvelope(Generic[Dataset]):
    dataset: str
    symbol: str
    data: Dataset
    observation_timestamp: datetime
    known_at: datetime
    retrieved_at: datetime
    status: str
    source: str
    quality_warnings: list[str] = field(default_factory=list)
    remaining_quota: int | None = None
    cached: bool = False

    def metadata(self) -> dict:
        return {
            "dataset": self.dataset,
            "symbol": self.symbol,
            "observationTimestamp": self.observation_timestamp.isoformat(),
            "knownAt": self.known_at.isoformat(),
            "retrievedAt": self.retrieved_at.isoformat(),
            "status": self.status,
            "source": self.source,
            "qualityWarnings": self.quality_warnings,
            "remainingQuota": self.remaining_quota,
            "cached": self.cached,
        }

