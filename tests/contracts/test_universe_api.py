from __future__ import annotations

import time
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gbb_terminal.api.routes.universes import create_universe_router
from gbb_terminal.storage.database import LocalMarketStore
from gbb_terminal.universe.models import (
    SectorConstituentResearch,
    SectorConstituentSnapshot,
    UniverseConstituent,
    UniverseKey,
    UniverseRefreshStatus,
    UniverseRefreshSummary,
    UniverseSnapshot,
    UniverseStatus,
)


NOW = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)


class _UniverseService:
    def __init__(self) -> None:
        self.snapshot = UniverseSnapshot(
            snapshot_id="snapshot-1",
            universe_key=UniverseKey.SP500,
            version=1,
            as_of_date=date(2026, 8, 16),
            source="Fixture Universe",
            source_url="https://example.test/sp500",
            known_at=NOW,
            retrieved_at=NOW,
            content_hash="fixture",
            constituent_count=1,
            constituents=[
                UniverseConstituent(
                    symbol="NVDA",
                    source_symbol="NVDA",
                    company_name="NVIDIA Corporation",
                    sector="Information Technology",
                    sub_industry="Semiconductors",
                    cik="1045810",
                )
            ],
            quality_warnings=["Current public composition snapshot."],
        )

    def status(self, universe_key: UniverseKey) -> UniverseStatus:
        return UniverseStatus(
            universe_key=universe_key,
            snapshot=self.snapshot,
            cached_count=1,
            completed_count=1,
            sector_counts={"Information Technology": 1},
            warnings=self.snapshot.quality_warnings,
        )

    async def refresh(self, universe_key, request, progress, _cancelled) -> UniverseRefreshSummary:
        assert universe_key == UniverseKey.SP500
        assert request.max_companies == 1
        progress(0.5, "NVDA")
        progress(1.0, None)
        return UniverseRefreshSummary(
            refresh_id="refresh-1",
            universe_key=universe_key,
            snapshot_id=self.snapshot.snapshot_id,
            status=UniverseRefreshStatus.COMPLETED,
            total_count=1,
            completed_count=1,
            partial_count=0,
            skipped_count=0,
            failed_count=0,
            cancelled_count=0,
            items=[],
            started_at=NOW,
            completed_at=NOW,
        )

    def sector_constituents(self, sector_symbol, universe_key) -> SectorConstituentSnapshot:
        assert sector_symbol.upper() == "XLK"
        record = SectorConstituentResearch(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            sector="Information Technology",
            sub_industry="Semiconductors",
            price=180,
            daily_change_percent=2.5,
            market_cap=4_000_000_000_000,
            market_cap_source="calculated_from_point_in_time_diluted_shares",
            data_status="completed",
            observation_timestamp=NOW,
            known_at=NOW,
        )
        return SectorConstituentSnapshot(
            universe_key=universe_key,
            snapshot_id=self.snapshot.snapshot_id,
            sector_symbol="XLK",
            sector_name="Information Technology",
            constituent_count=1,
            available_count=1,
            constituents=[record],
            gainers=[record],
            losers=[],
            unavailable=[],
            generated_at=NOW,
        )


def _client(tmp_path) -> TestClient:
    store = LocalMarketStore(tmp_path / "universe-api.duckdb")
    app = FastAPI()
    app.include_router(create_universe_router(_UniverseService(), store))
    return TestClient(app)


def test_universe_status_and_sector_contracts_use_camel_case(tmp_path):
    client = _client(tmp_path)

    status = client.get("/api/v3/universes/sp500")
    sector = client.get("/api/v3/universes/sp500/sectors/xlk/constituents")

    assert status.status_code == 200
    assert status.json()["apiVersion"] == "v3"
    assert status.json()["snapshot"]["constituentCount"] == 1
    assert "constituents" not in status.json()["snapshot"]
    assert status.json()["sectorCounts"] == {"Information Technology": 1}
    assert sector.status_code == 200
    assert sector.json()["sectorSymbol"] == "XLK"
    assert sector.json()["gainers"][0]["dailyChangePercent"] == 2.5
    assert sector.json()["gainers"][0]["marketCapSource"].startswith("calculated")


def test_universe_refresh_job_supports_progress_result_and_cancellation_contract(tmp_path):
    client = _client(tmp_path)

    with client:
        accepted = client.post(
            "/api/v3/universes/sp500/refresh",
            json={"maxCompanies": 1, "refreshSnapshot": False},
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["jobId"]
        for _ in range(100):
            job = client.get(f"/api/v3/universe-jobs/{job_id}")
            if job.json()["status"] != "running":
                break
            time.sleep(0.01)

    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert job.json()["result"]["completed_count"] == 1
    assert client.post(f"/api/v3/universe-jobs/{job_id}/cancel").json() == {
        "jobId": job_id,
        "cancelRequested": False,
    }
    assert client.get("/api/v3/universe-jobs/missing").status_code == 404
    assert client.post("/api/v3/universe-jobs/missing/cancel").status_code == 404
