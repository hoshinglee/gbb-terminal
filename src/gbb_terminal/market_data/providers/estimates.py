from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...intelligence.estimate_models import EstimateObservation
    from ...intelligence.models import CompanyIdentity


@runtime_checkable
class EstimateProvider(Protocol):
    provider_key: str
    name: str

    def estimates(
        self,
        company: CompanyIdentity,
        as_of: datetime,
    ) -> list[EstimateObservation]: ...

    def status(self) -> dict: ...


class ManualEstimateProvider:
    provider_key = "manual_fixture"
    name = "Manual Estimate Fixture"

    def __init__(self, observations: list[EstimateObservation] | None = None, source_path: Path | None = None) -> None:
        self._observations = list(observations or [])
        self.source_path = source_path

    @classmethod
    def from_path(cls, path: Path) -> "ManualEstimateProvider":
        if not path.exists():
            return cls(source_path=path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("observations", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Manual estimate fixtures must contain an observations list.")
        observations = [cls._observation(row) for row in rows]
        return cls(observations, path)

    def estimates(self, company: CompanyIdentity, as_of: datetime) -> list[EstimateObservation]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Estimate provider as-of timestamps must include a timezone.")
        symbols = {mapping.ticker for mapping in company.securities} | ({company.primary_ticker} if company.primary_ticker else set())
        return sorted(
            (
                observation
                for observation in self._observations
                if (observation.cik == company.cik or observation.symbol in symbols)
                and observation.known_at <= as_of
            ),
            key=lambda observation: (
                observation.period_end,
                observation.metric.value,
                observation.known_at,
                observation.estimate_id,
            ),
        )

    def status(self) -> dict:
        return {
            "provider": self.name,
            "providerKey": self.provider_key,
            "configured": bool(self._observations),
            "status": "Local Fixture" if self._observations else "No Coverage",
            "sourcePath": str(self.source_path) if self.source_path else None,
        }

    @classmethod
    def _observation(cls, row: dict) -> EstimateObservation:
        from ...intelligence.estimate_models import EstimateObservation

        payload = dict(row)
        payload.setdefault("provider_key", cls.provider_key)
        payload.setdefault("provider_name", cls.name)
        if not payload.get("estimate_id"):
            identity = {
                key: payload.get(key)
                for key in (
                    "provider_key",
                    "symbol",
                    "cik",
                    "metric",
                    "fiscal_year",
                    "fiscal_period",
                    "period_end",
                    "known_at",
                )
            }
            payload["estimate_id"] = hashlib.sha256(
                json.dumps(identity, sort_keys=True, default=str, separators=(",", ":")).encode()
            ).hexdigest()
        return EstimateObservation.model_validate(payload)


class EmptyEstimateProvider(ManualEstimateProvider):
    provider_key = "none"
    name = "No Estimate Provider"

    def __init__(self) -> None:
        super().__init__([])

    def estimates(self, company: CompanyIdentity, as_of: datetime) -> list[EstimateObservation]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Estimate provider as-of timestamps must include a timezone.")
        return []

    def status(self) -> dict:
        return {
            "provider": self.name,
            "providerKey": self.provider_key,
            "configured": False,
            "status": "No Coverage",
        }
