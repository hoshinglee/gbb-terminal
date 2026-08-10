from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from ..market_data.models import DataEnvelope
from ..market_data.providers.sec import SECProvider
from .identity import normalize_cik, normalize_exchange, normalize_ticker
from .models import CompanyIdentity, CompanyProvenance, CompanyRegistration
from .repository import CompanyIdentityRepository


@dataclass(frozen=True)
class IdentitySyncResult:
    companies_seen: int
    companies_created: int
    securities_seen: int
    securities_created: int


class CompanyIdentityService:
    def __init__(self, repository: CompanyIdentityRepository, sec: SECProvider) -> None:
        self.repository = repository
        self.sec = sec

    def resolve_ticker(
        self,
        ticker: str,
        as_of: date | None = None,
        include_historical: bool = True,
    ) -> CompanyIdentity | None:
        return self.repository.resolve_ticker(ticker, as_of=as_of, include_historical=include_historical)

    def resolve_cik(self, cik: str | int) -> CompanyIdentity | None:
        return self.repository.resolve_cik(cik)

    def sync_sec_directory(self) -> IdentitySyncResult:
        return self.ingest_sec_directory(self.sec.company_tickers())

    def ingest_sec_directory(self, envelope: DataEnvelope[list[dict]]) -> IdentitySyncResult:
        if envelope.dataset != "sec_company_tickers":
            raise ValueError("Company identity ingestion requires the SEC company-ticker directory.")
        provenance = CompanyProvenance(
            source=envelope.source,
            dataset=envelope.dataset,
            observation_timestamp=envelope.observation_timestamp,
            known_at=envelope.known_at,
            retrieved_at=envelope.retrieved_at,
            status=envelope.status,
            quality_warnings=envelope.quality_warnings,
            cached=envelope.cached,
        )
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in envelope.data:
            grouped[normalize_cik(row["cik"])].append(row)
        companies_before = self.repository.count_companies()
        securities_before = self.repository.count_securities()
        for cik, rows in grouped.items():
            normalized_rows = sorted(
                (
                    {
                        **row,
                        "ticker": normalize_ticker(row["ticker"]),
                        "exchange": normalize_exchange(row.get("exchange")),
                    }
                    for row in rows
                ),
                key=lambda row: (row["ticker"], row["exchange"] or ""),
            )
            existing = self.repository.resolve_cik(cik)
            existing_primary = existing.primary_ticker if existing else None
            primary = next(
                (row for row in normalized_rows if row["ticker"] == existing_primary),
                normalized_rows[0],
            )
            identity = self.repository.upsert_company(
                CompanyRegistration(
                    cik=cik,
                    legal_name=primary["legalName"],
                    primary_ticker=primary["ticker"],
                    exchange=primary["exchange"],
                    effective_from=envelope.observation_timestamp.date(),
                    provenance=provenance,
                )
            )
            for row in normalized_rows:
                if row["ticker"] == identity.primary_ticker and row["exchange"] == identity.exchange:
                    continue
                self.repository.register_security(
                    identity.company_id,
                    row["ticker"],
                    row["exchange"],
                    envelope.observation_timestamp.date(),
                    provenance,
                )
        companies_after = self.repository.count_companies()
        securities_after = self.repository.count_securities()
        return IdentitySyncResult(
            companies_seen=len(grouped),
            companies_created=companies_after - companies_before,
            securities_seen=len(envelope.data),
            securities_created=securities_after - securities_before,
        )
