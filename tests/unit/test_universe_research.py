from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from gbb_terminal.intelligence.repository import CompanyIdentityRepository
from gbb_terminal.intelligence.service import CompanyIdentityService
from gbb_terminal.market_data.models import DataEnvelope
from gbb_terminal.market_data.providers.base import ProviderUnavailable
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.universe.models import (
    UniverseConstituent,
    UniverseItemStatus,
    UniverseKey,
    UniverseRefreshRequest,
    UniverseRefreshStatus,
    UniverseSourceSnapshot,
)
from gbb_terminal.universe.providers import UniverseProvider, WikipediaSP500Provider
from gbb_terminal.universe.repository import UniverseRepository
from gbb_terminal.universe.service import UniverseResearchService


NOW = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)


def _constituent(symbol: str, cik: int, sector: str = "Information Technology") -> UniverseConstituent:
    return UniverseConstituent(
        symbol=symbol,
        source_symbol=symbol,
        company_name=f"{symbol} Corporation",
        sector=sector,
        sub_industry="Research Software",
        cik=cik,
        date_added=date(2020, 1, 1),
    )


def _snapshot(*constituents: UniverseConstituent, content_hash: str = "fixture-v1") -> UniverseSourceSnapshot:
    return UniverseSourceSnapshot(
        universe_key=UniverseKey.SP500,
        as_of_date=NOW.date(),
        source="Fixture Universe",
        source_url="https://example.test/sp500",
        known_at=NOW,
        retrieved_at=NOW,
        content_hash=content_hash,
        constituents=list(constituents),
        quality_warnings=["Current composition fixture; not historical membership."],
    )


def _history(last: float, previous: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [previous - 1, last - 1],
            "High": [previous + 1, last + 1],
            "Low": [previous - 2, last - 2],
            "Close": [previous, last],
            "Volume": [1_000_000, 1_200_000],
        },
        index=pd.to_datetime(["2026-08-13", "2026-08-14"]),
    )


def _envelope(dataset: str, symbol: str, data):
    return DataEnvelope(
        dataset=dataset,
        symbol=symbol,
        data=data,
        observation_timestamp=NOW,
        known_at=NOW,
        retrieved_at=NOW,
        status="Delayed",
        source="Fixture Provider",
    )


class _FixtureUniverseProvider(UniverseProvider):
    def __init__(self, snapshot: UniverseSourceSnapshot) -> None:
        self.snapshot = snapshot

    def fetch_snapshot(self, universe_key: UniverseKey) -> UniverseSourceSnapshot:
        assert universe_key == UniverseKey.SP500
        return self.snapshot


class _FixtureYahoo:
    def history(self, symbol: str, _period: str):
        if symbol == "CFAIL":
            raise ProviderUnavailable("Fixture Yahoo failure.")
        if symbol == "BPART":
            return _envelope("daily_prices", symbol, _history(90, 100))
        return _envelope("daily_prices", symbol, _history(110, 100))


class _FixtureSEC:
    name = "Fixture SEC"

    def company_facts(self, cik: str):
        if cik != "0000000001":
            raise ProviderUnavailable("Fixture Company Facts failure.")
        return _envelope("sec_company_facts", cik, {"facts": {}})

    def submissions(self, cik: str):
        if cik != "0000000001":
            raise ProviderUnavailable("Fixture submissions failure.")
        return _envelope("sec_submissions", cik, {"filings": {"recent": {}}})


class _FixtureFacts:
    def __init__(self) -> None:
        self.sec = _FixtureSEC()
        self.ingested: set[str] = set()

    def ingest_company_facts(self, company, _facts, _submissions) -> None:
        self.ingested.add(company.primary_ticker)


class _FixtureMetrics:
    def __init__(self, facts: _FixtureFacts) -> None:
        self.facts = facts

    def calculate(self, ticker: str, period_kind):
        if ticker not in self.facts.ingested:
            raise ValueError("No fixture facts were ingested.")
        return SimpleNamespace(metrics=[SimpleNamespace(value=1.0)], period_kind=period_kind)


class _FixtureValuation:
    def calculate(self, ticker: str, _history, **_kwargs):
        market_cap = 2_000_000_000 if ticker == "AGOOD" else 1_000_000_000
        return SimpleNamespace(points={"price_to_sales": [SimpleNamespace(value=4.0, market_cap=market_cap)]})


class _FixtureEarnings:
    def analyze(self, *_args, **_kwargs):
        return SimpleNamespace(events=[SimpleNamespace(reaction=SimpleNamespace(anchor_session=date(2026, 5, 1)))])


def _service(tmp_path) -> UniverseResearchService:
    store = LocalMarketStore(tmp_path / "universe.duckdb")
    repository = UniverseRepository(store.connection)
    snapshot = _snapshot(
        _constituent("AGOOD", 1),
        _constituent("BPART", 2),
        _constituent("CFAIL", 3),
    )
    identities = CompanyIdentityService(CompanyIdentityRepository(store.connection), _FixtureSEC())
    facts = _FixtureFacts()
    market_data = SimpleNamespace(store=store, metadata={}, yahoo=_FixtureYahoo())
    return UniverseResearchService(
        repository,
        _FixtureUniverseProvider(snapshot),
        identities,
        facts,
        _FixtureMetrics(facts),
        _FixtureValuation(),
        _FixtureEarnings(),
        market_data,
    )


def test_wikipedia_provider_parses_and_normalizes_current_constituents():
    rows = [
        "<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>Multi-Sector Holdings</td>"
        "<td>Omaha</td><td>2010-02-16</td><td>1067983</td><td>1839</td></tr>"
    ]
    rows.extend(
        f"<tr><td>T{index:03d}</td><td>Company {index}</td><td>Information Technology</td>"
        f"<td>Software</td><td>New York</td><td></td><td>{index + 1}</td><td>2000</td></tr>"
        for index in range(400)
    )
    html = (
        '<table id="constituents"><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th>'
        '<th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th>'
        f"<th>Founded</th></tr>{''.join(rows)}</table>"
    )
    provider = WikipediaSP500Provider()
    provider.request_bytes = lambda _url: html.encode()

    result = provider.fetch_snapshot(UniverseKey.SP500)

    assert len(result.constituents) == 401
    assert result.constituents[0].symbol == "BRK-B"
    assert result.constituents[0].source_symbol == "BRK.B"
    assert result.constituents[0].cik == "0001067983"
    assert "not a licensed historical" in result.quality_warnings[0]


def test_universe_repository_versions_changed_snapshots_and_reuses_identical_content(tmp_path):
    repository = UniverseRepository(LocalMarketStore(tmp_path / "snapshots.duckdb").connection)
    first_source = _snapshot(_constituent("AAA", 1))
    first = repository.save_snapshot(first_source)
    duplicate = repository.save_snapshot(first_source)
    second = repository.save_snapshot(
        _snapshot(_constituent("AAA", 1), _constituent("BBB", 2), content_hash="fixture-v2")
    )

    assert duplicate.snapshot_id == first.snapshot_id
    assert first.version == 1
    assert second.version == 2
    assert repository.latest_snapshot(UniverseKey.SP500).snapshot_id == second.snapshot_id


@pytest.mark.asyncio
async def test_universe_refresh_is_partial_resumable_and_sector_ranked(tmp_path):
    service = _service(tmp_path)

    first = await service.refresh(
        request=UniverseRefreshRequest(max_attempts=1, concurrency=2),
    )

    assert first.status == UniverseRefreshStatus.PARTIAL
    assert first.completed_count == 1
    assert first.partial_count == 1
    assert first.failed_count == 1
    assert {item.symbol: item.status for item in first.items} == {
        "AGOOD": UniverseItemStatus.COMPLETED,
        "BPART": UniverseItemStatus.PARTIAL,
        "CFAIL": UniverseItemStatus.FAILED,
    }
    sector = service.sector_constituents("XLK")
    assert [item.symbol for item in sector.gainers] == ["AGOOD"]
    assert [item.symbol for item in sector.losers] == ["BPART"]
    assert [item.symbol for item in sector.unavailable] == ["CFAIL"]
    assert sector.gainers[0].market_cap == 2_000_000_000

    resumed = await service.refresh(
        request=UniverseRefreshRequest(
            refresh_snapshot=False,
            max_companies=1,
            max_attempts=1,
        ),
    )
    assert resumed.skipped_count == 1
    assert resumed.items[0].status == UniverseItemStatus.SKIPPED


@pytest.mark.asyncio
async def test_universe_refresh_honors_cancellation_before_company_downloads(tmp_path):
    service = _service(tmp_path)

    result = await service.refresh(
        request=UniverseRefreshRequest(max_companies=2, max_attempts=1),
        cancelled=lambda: True,
    )

    assert result.status == UniverseRefreshStatus.CANCELLED
    assert result.cancelled_count == 2
    assert all(item.status == UniverseItemStatus.CANCELLED for item in result.items)


@pytest.mark.asyncio
async def test_universe_refresh_reconciles_processing_exceptions_to_failed(tmp_path, monkeypatch):
    service = _service(tmp_path)

    def fail_processing(*_args, **_kwargs):
        raise RuntimeError("Fixture processing failure.")

    monkeypatch.setattr(service, "_persist_item", fail_processing)
    result = await service.refresh(
        request=UniverseRefreshRequest(max_companies=1, max_attempts=1),
    )

    assert result.status == UniverseRefreshStatus.FAILED
    assert result.failed_count == 1
    assert result.items[0].status == UniverseItemStatus.FAILED
    assert result.items[0].stage == "processing_failed"
    assert all(
        item.status not in {UniverseItemStatus.QUEUED, UniverseItemStatus.RUNNING}
        for item in result.items
    )
