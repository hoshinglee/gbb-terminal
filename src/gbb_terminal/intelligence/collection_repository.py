from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import duckdb

from .collection_models import (
    COLLECTION_MODEL_VERSION,
    IntelligenceRefreshItem,
    IntelligenceRefreshRequest,
    IntelligenceRefreshStatus,
    IntelligenceRefreshSummary,
    ModuleCoverage,
)


class IntelligenceRefreshRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def start(self, company_id: str, ticker: str, request: IntelligenceRefreshRequest) -> str:
        if self.connection.execute("SELECT 1 FROM companies WHERE company_id = ?", [company_id]).fetchone() is None:
            raise LookupError(f"No canonical company exists for company_id {company_id}.")
        refresh_id = str(uuid4())
        now = self._utc_now()
        self.connection.execute(
            """INSERT INTO intelligence_refresh_runs
               (refresh_id, company_id, ticker, status, request, documents_discovered, documents_downloaded,
                documents_unchanged, documents_parsed, documents_failed, relationship_count,
                operating_observation_count, guidance_statement_count, coverage, warnings, model_version,
                started_at, completed_at)
               VALUES (?, ?, ?, 'running', ?, 0, 0, 0, 0, 0, 0, 0, 0, '[]', '[]', ?, ?, NULL)""",
            [refresh_id, company_id, ticker.upper(), json.dumps(request.model_dump(mode="json")), COLLECTION_MODEL_VERSION, now],
        )
        return refresh_id

    def add_item(
        self,
        refresh_id: str,
        external_id: str,
        status,
        source_url: str | None = None,
        accession_number: str | None = None,
        form: str | None = None,
        document_id: str | None = None,
        reason: str | None = None,
    ) -> IntelligenceRefreshItem:
        item_id = str(uuid4())
        self.connection.execute(
            """INSERT INTO intelligence_refresh_items
               (item_id, refresh_id, external_id, source_url, accession_number, form, status,
                document_id, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                item_id,
                refresh_id,
                external_id,
                source_url,
                accession_number,
                form,
                status.value,
                document_id,
                reason,
                self._utc_now(),
            ],
        )
        return self._item(item_id)

    def finish(
        self,
        refresh_id: str,
        status: IntelligenceRefreshStatus,
        counts: dict[str, int],
        coverage: list[ModuleCoverage],
        warnings: list[str],
    ) -> IntelligenceRefreshSummary:
        if status == IntelligenceRefreshStatus.RUNNING:
            raise ValueError("A finished intelligence refresh cannot remain running.")
        self.connection.execute(
            """UPDATE intelligence_refresh_runs SET
                 status = ?, documents_discovered = ?, documents_downloaded = ?, documents_unchanged = ?,
                 documents_parsed = ?, documents_failed = ?, relationship_count = ?,
                 operating_observation_count = ?, guidance_statement_count = ?, coverage = ?, warnings = ?,
                 completed_at = ?
               WHERE refresh_id = ?""",
            [
                status.value,
                counts.get("documents_discovered", 0),
                counts.get("documents_downloaded", 0),
                counts.get("documents_unchanged", 0),
                counts.get("documents_parsed", 0),
                counts.get("documents_failed", 0),
                counts.get("relationship_count", 0),
                counts.get("operating_observation_count", 0),
                counts.get("guidance_statement_count", 0),
                json.dumps([item.model_dump(mode="json") for item in coverage]),
                json.dumps(list(dict.fromkeys(warnings))),
                self._utc_now(),
                refresh_id,
            ],
        )
        return self.get(refresh_id)

    def get(self, refresh_id: str) -> IntelligenceRefreshSummary:
        row = self.connection.execute(
            """SELECT refresh_id, company_id, ticker, status, documents_discovered, documents_downloaded,
                      documents_unchanged, documents_parsed, documents_failed, relationship_count,
                      operating_observation_count, guidance_statement_count, coverage, warnings, model_version,
                      started_at, completed_at
               FROM intelligence_refresh_runs WHERE refresh_id = ?""",
            [refresh_id],
        ).fetchone()
        if row is None:
            raise LookupError(f"No intelligence refresh exists for refresh_id {refresh_id}.")
        return IntelligenceRefreshSummary(
            refresh_id=row[0],
            company_id=row[1],
            ticker=row[2],
            status=row[3],
            documents_discovered=row[4],
            documents_downloaded=row[5],
            documents_unchanged=row[6],
            documents_parsed=row[7],
            documents_failed=row[8],
            relationship_count=row[9],
            operating_observation_count=row[10],
            guidance_statement_count=row[11],
            coverage=[ModuleCoverage.model_validate(item) for item in json.loads(row[12])],
            warnings=json.loads(row[13]),
            model_version=row[14],
            started_at=self._aware_utc(row[15]),
            completed_at=self._aware_utc(row[16]),
            items=self.items(refresh_id),
        )

    def latest(self, company_id: str) -> IntelligenceRefreshSummary | None:
        row = self.connection.execute(
            """SELECT refresh_id FROM intelligence_refresh_runs
               WHERE company_id = ? ORDER BY started_at DESC LIMIT 1""",
            [company_id],
        ).fetchone()
        return self.get(row[0]) if row else None

    def items(self, refresh_id: str) -> list[IntelligenceRefreshItem]:
        rows = self.connection.execute(
            """SELECT item_id, refresh_id, external_id, source_url, accession_number, form, status,
                      document_id, reason, created_at
               FROM intelligence_refresh_items WHERE refresh_id = ? ORDER BY created_at, external_id""",
            [refresh_id],
        ).fetchall()
        return [
            IntelligenceRefreshItem(
                item_id=row[0],
                refresh_id=row[1],
                external_id=row[2],
                source_url=row[3],
                accession_number=row[4],
                form=row[5],
                status=row[6],
                document_id=row[7],
                reason=row[8],
                created_at=self._aware_utc(row[9]),
            )
            for row in rows
        ]

    def _item(self, item_id: str) -> IntelligenceRefreshItem:
        row = self.connection.execute(
            """SELECT item_id, refresh_id, external_id, source_url, accession_number, form, status,
                      document_id, reason, created_at
               FROM intelligence_refresh_items WHERE item_id = ?""",
            [item_id],
        ).fetchone()
        return IntelligenceRefreshItem(
            item_id=row[0],
            refresh_id=row[1],
            external_id=row[2],
            source_url=row[3],
            accession_number=row[4],
            form=row[5],
            status=row[6],
            document_id=row[7],
            reason=row[8],
            created_at=self._aware_utc(row[9]),
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _aware_utc(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None else None
