from __future__ import annotations

from datetime import datetime, timezone

from ..models import DataEnvelope
from .base import BaseProvider


class SECProvider(BaseProvider):
    name = "SEC EDGAR"

    def submissions(self, cik: str) -> DataEnvelope[dict]:
        normalized = "".join(character for character in cik if character.isdigit()).zfill(10)
        payload = self.request_json(f"https://data.sec.gov/submissions/CIK{normalized}.json")
        retrieved_at = datetime.now(timezone.utc)
        recent = payload.get("filings", {}).get("recent", {})
        accepted = recent.get("acceptanceDateTime", [])
        known_at = datetime.fromisoformat(accepted[0].replace("Z", "+00:00")) if accepted else retrieved_at
        return DataEnvelope("sec_submissions", normalized, payload, known_at, known_at, retrieved_at, self.delayed_status, self.name, ["Filings become usable only at SEC acceptance time; report-period dates are not publication dates."])

    @staticmethod
    def recent_forms(payload: dict, forms: set[str]) -> list[dict]:
        recent = payload.get("filings", {}).get("recent", {})
        keys = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument")
        rows = [dict(zip(keys, values)) for values in zip(*(recent.get(key, []) for key in keys))]
        return [row for row in rows if row["form"] in forms]

