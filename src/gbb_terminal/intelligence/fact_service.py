from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from ..market_data.models import DataEnvelope
from ..market_data.providers.sec import SECProvider
from ..market_data.providers.base import ProviderUnavailable
from ..storage.database import LocalMarketStore
from .fact_models import FinancialFact, FinancialFactQuery
from .fact_repository import FinancialFactRepository
from .models import CompanyIdentity, CompanyProvenance
from .service import CompanyIdentityService


@dataclass(frozen=True)
class FactIngestionResult:
    company_id: str
    cik: str
    observations_seen: int
    observations_inserted: int
    observations_skipped: int


class FinancialFactService:
    def __init__(
        self,
        repository: FinancialFactRepository,
        identities: CompanyIdentityService,
        store: LocalMarketStore,
        sec: SECProvider,
    ) -> None:
        self.repository = repository
        self.identities = identities
        self.store = store
        self.sec = sec

    def sync_company_facts(self, ticker_or_cik: str) -> FactIngestionResult:
        company = self._resolve_company(ticker_or_cik)
        try:
            facts = self.sec.company_facts(company.cik)
            self.store.save_provider_payload(facts.metadata(), facts.data)
        except ProviderUnavailable as error:
            facts = self._cached_envelope("sec_company_facts", company.cik, error)
        try:
            submissions = self.sec.submissions(company.cik)
            self.store.save_provider_payload(submissions.metadata(), submissions.data)
        except ProviderUnavailable as error:
            submissions = self._cached_envelope("sec_submissions", company.cik, error, required=False)
        return self.ingest_company_facts(company, facts, submissions)

    def ingest_company_facts(
        self,
        company: CompanyIdentity,
        facts: DataEnvelope[dict],
        submissions: DataEnvelope[dict] | None = None,
    ) -> FactIngestionResult:
        if facts.dataset != "sec_company_facts":
            raise ValueError("Financial fact ingestion requires an SEC Company Facts payload.")
        if facts.symbol != company.cik:
            raise ValueError("The SEC Company Facts CIK does not match the canonical company.")
        acceptance_times = SECProvider.acceptance_times(submissions.data) if submissions else {}
        parsed: list[FinancialFact] = []
        skipped = 0
        payload_facts = facts.data.get("facts", {})
        for taxonomy, concepts in payload_facts.items():
            for concept, definition in concepts.items():
                for unit, observations in definition.get("units", {}).items():
                    for observation in observations:
                        try:
                            parsed.append(
                                self._parse_fact(
                                    company,
                                    taxonomy,
                                    concept,
                                    definition,
                                    unit,
                                    observation,
                                    facts,
                                    acceptance_times,
                                )
                            )
                        except (KeyError, TypeError, ValueError):
                            skipped += 1
        inserted = self.repository.save_facts(parsed)
        return FactIngestionResult(
            company_id=company.company_id,
            cik=company.cik,
            observations_seen=len(parsed) + skipped,
            observations_inserted=inserted,
            observations_skipped=skipped,
        )

    def history(
        self,
        ticker_or_cik: str,
        query: FinancialFactQuery | None = None,
    ) -> list[FinancialFact]:
        company = self._resolve_company(ticker_or_cik)
        return self.repository.query_facts(company.company_id, query)

    def _resolve_company(self, ticker_or_cik: str) -> CompanyIdentity:
        company = (
            self.identities.resolve_cik(ticker_or_cik)
            if ticker_or_cik.upper().removeprefix("CIK").strip().isdigit()
            else self.identities.resolve_ticker(ticker_or_cik)
        )
        if company is None:
            raise ValueError(f"No canonical company identity exists for {ticker_or_cik}.")
        return company

    def _cached_envelope(
        self,
        dataset: str,
        cik: str,
        error: Exception,
        required: bool = True,
    ) -> DataEnvelope[dict] | None:
        cached = self.store.load_provider_payload(self.sec.name, dataset, cik)
        if cached is None:
            if required:
                raise error
            return None
        metadata = cached["metadata"]
        return DataEnvelope(
            dataset=dataset,
            symbol=cik,
            data=cached["data"],
            observation_timestamp=self._timestamp(metadata["observationTimestamp"]),
            known_at=self._timestamp(metadata["knownAt"]),
            retrieved_at=self._timestamp(metadata["retrievedAt"]),
            status="Stale Cache",
            source=metadata["source"],
            quality_warnings=[*metadata.get("qualityWarnings", []), str(error)],
            remaining_quota=metadata.get("remainingQuota"),
            cached=True,
        )

    @staticmethod
    def _timestamp(value: str) -> datetime:
        timestamp = datetime.fromisoformat(value)
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

    @classmethod
    def _parse_fact(
        cls,
        company: CompanyIdentity,
        taxonomy: str,
        concept: str,
        definition: dict,
        unit: str,
        observation: dict,
        envelope: DataEnvelope[dict],
        acceptance_times: dict[str, datetime],
    ) -> FinancialFact:
        accession = str(observation["accn"])
        period_end = date.fromisoformat(observation["end"])
        filed_date = date.fromisoformat(observation["filed"])
        form = str(observation["form"]).upper()
        raw_value = str(observation["val"])
        value = float(observation["val"])
        accepted_at = acceptance_times.get(accession)
        if accepted_at:
            known_at = accepted_at
            known_at_source = "acceptance"
            warnings = list(envelope.quality_warnings)
        else:
            known_at = datetime.combine(filed_date, time.max, tzinfo=timezone.utc)
            known_at_source = "filed_date_fallback"
            warnings = [
                *envelope.quality_warnings,
                "Exact SEC acceptance time was unavailable; known_at conservatively uses the end of the filed date.",
            ]
        identity = {
            "companyId": company.company_id,
            "taxonomy": taxonomy,
            "concept": concept,
            "unit": unit,
            "accession": accession,
            "start": observation.get("start"),
            "end": observation["end"],
            "fy": observation.get("fy"),
            "fp": observation.get("fp"),
            "form": form,
            "frame": observation.get("frame"),
        }
        fact_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return FinancialFact(
            fact_id=fact_id,
            company_id=company.company_id,
            cik=company.cik,
            taxonomy=taxonomy,
            concept=concept,
            label=definition.get("label"),
            description=definition.get("description"),
            value=value,
            raw_value=raw_value,
            unit=unit,
            period_start=date.fromisoformat(observation["start"]) if observation.get("start") else None,
            period_end=period_end,
            fiscal_year=observation.get("fy"),
            fiscal_period=observation.get("fp"),
            form=form,
            filed_date=filed_date,
            accepted_at=accepted_at,
            known_at_source=known_at_source,
            accession_number=accession,
            frame=observation.get("frame"),
            provenance=CompanyProvenance(
                source=envelope.source,
                dataset=envelope.dataset,
                observation_timestamp=datetime.combine(period_end, time.min, tzinfo=timezone.utc),
                known_at=known_at,
                retrieved_at=envelope.retrieved_at,
                status=envelope.status,
                quality_warnings=warnings,
                remaining_quota=envelope.remaining_quota,
                cached=envelope.cached,
            ),
            source_metadata={
                "accessionNumber": accession,
                "filedDate": filed_date.isoformat(),
                "acceptedAt": accepted_at.isoformat() if accepted_at else None,
                "knownAtSource": known_at_source,
                "frame": observation.get("frame"),
                "form": form,
            },
        )
