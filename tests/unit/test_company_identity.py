from datetime import date, datetime, timezone

import pytest

from gbb_terminal.intelligence import (
    CompanyIdentityRepository,
    CompanyIdentityService,
    CompanyProvenance,
    CompanyRegistration,
    CompanyStatus,
    IdentityConflictError,
    normalize_cik,
    normalize_ticker,
)
from gbb_terminal.market_data.models import DataEnvelope
from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.storage.database import LocalMarketStore


def provenance(observed: datetime | None = None) -> CompanyProvenance:
    timestamp = observed or datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    return CompanyProvenance(
        source="SEC EDGAR",
        dataset="sec_company_tickers",
        observation_timestamp=timestamp,
        known_at=timestamp,
        retrieved_at=timestamp,
        status="Delayed Public Data",
        quality_warnings=["Association effective dates are not supplied by the SEC directory."],
    )


def registration(**updates) -> CompanyRegistration:
    values = {
        "cik": "0001045810",
        "legal_name": "NVIDIA CORP",
        "primary_ticker": "NVDA",
        "exchange": "Nasdaq",
        "sector": "Technology",
        "industry": "Semiconductors",
        "fiscal_year_end": "0128",
        "effective_from": date(1999, 1, 22),
        "provenance": provenance(),
    }
    return CompanyRegistration.model_validate({**values, **updates})


def repository(tmp_path) -> CompanyIdentityRepository:
    return CompanyIdentityRepository(LocalMarketStore(tmp_path / "identity.duckdb").connection)


def test_ticker_and_cik_normalization():
    assert normalize_ticker(" nvda ") == "NVDA"
    assert normalize_ticker("$brk.b") == "BRK-B"
    assert normalize_cik("CIK 320193") == "0000320193"
    assert normalize_cik(1045810) == "0001045810"
    with pytest.raises(ValueError, match="Ticker"):
        normalize_ticker("NVDA/US")
    with pytest.raises(ValueError, match="CIK"):
        normalize_cik("not-a-cik")
    with pytest.raises(ValueError, match="timezone"):
        CompanyProvenance(
            source="Fixture",
            observation_timestamp=datetime(2026, 8, 10),
            known_at=datetime(2026, 8, 10),
            retrieved_at=datetime(2026, 8, 10),
        )


def test_ticker_and_cik_resolve_to_one_canonical_company(tmp_path):
    identities = repository(tmp_path)
    created = identities.upsert_company(registration())

    by_ticker = identities.resolve_ticker("nvda")
    by_cik = identities.resolve_cik("1045810")

    assert by_ticker is not None and by_cik is not None
    assert by_ticker.company_id == created.company_id == by_cik.company_id
    assert by_ticker.primary_ticker == "NVDA"
    assert by_ticker.exchange == "NASDAQ"
    assert by_ticker.fiscal_year_end == "01-28"
    assert by_ticker.provenance.source == "SEC EDGAR"


def test_duplicate_registration_updates_identity_without_creating_duplicates(tmp_path):
    identities = repository(tmp_path)
    created = identities.upsert_company(registration())
    updated = identities.upsert_company(
        registration(
            legal_name="NVIDIA CORPORATION",
            industry="Semiconductor Manufacturing",
            provenance=provenance(datetime(2026, 8, 11, 12, tzinfo=timezone.utc)),
        )
    )

    assert updated.company_id == created.company_id
    assert updated.legal_name == "NVIDIA CORPORATION"
    assert updated.industry == "Semiconductor Manufacturing"
    assert identities.count_companies() == 1
    assert identities.count_securities() == 1
    assert updated.provenance.observation_timestamp.date() == date(2026, 8, 11)


def test_duplicate_active_ticker_for_another_cik_is_rejected(tmp_path):
    identities = repository(tmp_path)
    identities.upsert_company(registration())

    with pytest.raises(IdentityConflictError, match="already assigned"):
        identities.upsert_company(registration(cik="0000320193", legal_name="APPLE INC"))

    assert identities.count_companies() == 1
    assert identities.count_securities() == 1


def test_ticker_change_and_delisting_preserve_history(tmp_path):
    identities = repository(tmp_path)
    created = identities.upsert_company(
        registration(primary_ticker="OLD", exchange="NYSE", effective_from=date(2000, 1, 1))
    )
    changed = identities.change_primary_ticker(
        created.company_id,
        "NEW",
        "Nasdaq",
        date(2020, 1, 2),
        provenance(datetime(2020, 1, 2, 20, tzinfo=timezone.utc)),
    )

    assert changed.company_id == created.company_id
    assert changed.primary_ticker == "NEW"
    assert identities.resolve_ticker("OLD", as_of=date(2019, 12, 31)).company_id == created.company_id
    assert identities.resolve_ticker("NEW").company_id == created.company_id
    assert len(changed.securities) == 2
    assert changed.securities[0].valid_to == date(2020, 1, 1)

    inactive = identities.mark_inactive(
        created.company_id,
        date(2026, 7, 31),
        provenance(datetime(2026, 8, 1, 12, tzinfo=timezone.utc)),
    )
    assert inactive.status == CompanyStatus.INACTIVE
    assert identities.resolve_ticker("NEW", include_historical=False) is None
    assert identities.resolve_ticker("NEW").company_id == created.company_id
    assert inactive.securities[-1].valid_to == date(2026, 7, 31)


def test_delisted_ticker_can_be_reused_without_rewriting_the_earlier_company(tmp_path):
    identities = repository(tmp_path)
    earlier = identities.upsert_company(
        registration(primary_ticker="REUSE", exchange="NYSE", effective_from=date(2000, 1, 1))
    )
    identities.mark_inactive(earlier.company_id, date(2010, 12, 31), provenance())
    later = identities.upsert_company(
        registration(
            cik="0000320193",
            legal_name="NEW LISTED COMPANY",
            primary_ticker="REUSE",
            exchange="Nasdaq",
            effective_from=date(2020, 1, 2),
        )
    )

    assert identities.resolve_ticker("REUSE").company_id == later.company_id
    assert identities.resolve_ticker("REUSE", as_of=date(2005, 6, 1)).company_id == earlier.company_id
    assert identities.resolve_cik("0001045810").company_id == earlier.company_id


def test_sec_directory_ingestion_groups_multiple_securities_under_one_company(tmp_path):
    identities = repository(tmp_path)
    service = CompanyIdentityService(identities, SECProvider())
    observed = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    envelope = DataEnvelope(
        dataset="sec_company_tickers",
        symbol="US",
        data=[
            {"cik": 1652044, "legalName": "Alphabet Inc.", "ticker": "GOOGL", "exchange": "Nasdaq"},
            {"cik": 1652044, "legalName": "Alphabet Inc.", "ticker": "GOOG", "exchange": "Nasdaq"},
        ],
        observation_timestamp=observed,
        known_at=observed,
        retrieved_at=observed,
        status="Delayed Public Data",
        source="SEC EDGAR",
        quality_warnings=["Directory coverage is not guaranteed."],
    )

    first = service.ingest_sec_directory(envelope)
    second = service.ingest_sec_directory(envelope)

    goog = service.resolve_ticker("GOOG")
    googl = service.resolve_ticker("GOOGL")
    assert goog is not None and googl is not None
    assert goog.company_id == googl.company_id
    assert first.companies_created == 1
    assert first.securities_created == 2
    assert second.companies_created == 0
    assert second.securities_created == 0
    assert identities.count_companies() == 1
    assert identities.count_securities() == 2
