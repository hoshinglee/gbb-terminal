from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import duckdb

from .identity import IdentityConflictError, normalize_cik, normalize_exchange, normalize_ticker
from .models import CompanyIdentity, CompanyProvenance, CompanyRegistration, CompanyStatus, SecurityMapping


class CompanyIdentityRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection

    def upsert_company(self, registration: CompanyRegistration) -> CompanyIdentity:
        self.connection.execute("BEGIN TRANSACTION")
        try:
            company_row = self.connection.execute(
                "SELECT company_id FROM companies WHERE cik = ?",
                [registration.cik],
            ).fetchone()
            ticker_row = self._active_ticker_owner(registration.primary_ticker)
            if company_row and ticker_row and company_row[0] != ticker_row[0]:
                raise IdentityConflictError(
                    f"Ticker {registration.primary_ticker} is already assigned to another company."
                )
            company_id = company_row[0] if company_row else str(uuid4())
            now = self._utc_now()
            provenance = self._dump_provenance(registration.provenance)
            if company_row:
                self.connection.execute(
                    """UPDATE companies
                       SET legal_name = ?, sector = coalesce(?, sector), industry = coalesce(?, industry),
                           fiscal_year_end = coalesce(?, fiscal_year_end), status = ?, provenance = ?, updated_at = ?
                       WHERE company_id = ?""",
                    [
                        registration.legal_name,
                        registration.sector,
                        registration.industry,
                        registration.fiscal_year_end,
                        CompanyStatus.ACTIVE.value,
                        provenance,
                        now,
                        company_id,
                    ],
                )
            else:
                self.connection.execute(
                    """INSERT INTO companies
                       (company_id, cik, legal_name, sector, industry, fiscal_year_end, status, provenance,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        company_id,
                        registration.cik,
                        registration.legal_name,
                        registration.sector,
                        registration.industry,
                        registration.fiscal_year_end,
                        CompanyStatus.ACTIVE.value,
                        provenance,
                        now,
                        now,
                    ],
                )
            current_primary = self._active_primary(company_id)
            if current_primary is None:
                self._register_security(
                    company_id,
                    registration.primary_ticker,
                    registration.exchange,
                    registration.effective_from,
                    True,
                    registration.provenance,
                )
            elif current_primary[1] == registration.primary_ticker and current_primary[2] == registration.exchange:
                self._refresh_security(current_primary[0], registration.provenance)
            else:
                self._register_security(
                    company_id,
                    registration.primary_ticker,
                    registration.exchange,
                    registration.effective_from,
                    False,
                    registration.provenance,
                )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_company(company_id)

    def register_security(
        self,
        company_id: str,
        ticker: str,
        exchange: str | None,
        effective_from: date,
        provenance: CompanyProvenance,
    ) -> CompanyIdentity:
        normalized_ticker = normalize_ticker(ticker)
        normalized_exchange = normalize_exchange(exchange)
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self._require_company(company_id)
            self._register_security(
                company_id,
                normalized_ticker,
                normalized_exchange,
                effective_from,
                False,
                provenance,
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_company(company_id)

    def change_primary_ticker(
        self,
        company_id: str,
        ticker: str,
        exchange: str | None,
        effective_from: date,
        provenance: CompanyProvenance,
    ) -> CompanyIdentity:
        normalized_ticker = normalize_ticker(ticker)
        normalized_exchange = normalize_exchange(exchange)
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self._require_company(company_id)
            owner = self._active_ticker_owner(normalized_ticker)
            if owner and owner[0] != company_id:
                raise IdentityConflictError(f"Ticker {normalized_ticker} is already assigned to another company.")
            current_primary = self._active_primary(company_id)
            if current_primary and current_primary[1] == normalized_ticker and current_primary[2] == normalized_exchange:
                self._refresh_security(current_primary[0], provenance)
                self.connection.execute("COMMIT")
                return self.get_company(company_id)
            active_rows = self.connection.execute(
                """SELECT security_id, valid_from FROM company_security_mappings
                   WHERE company_id = ? AND status = 'active' AND (is_primary OR ticker = ?)""",
                [company_id, normalized_ticker],
            ).fetchall()
            for security_id, valid_from in active_rows:
                if effective_from <= valid_from:
                    raise ValueError("A ticker change must occur after the existing mapping begins.")
                self.connection.execute(
                    """UPDATE company_security_mappings
                       SET valid_to = ?, status = 'inactive', updated_at = ? WHERE security_id = ?""",
                    [effective_from - timedelta(days=1), self._utc_now(), security_id],
                )
            self._register_security(
                company_id,
                normalized_ticker,
                normalized_exchange,
                effective_from,
                True,
                provenance,
            )
            self.connection.execute(
                "UPDATE companies SET status = 'active', provenance = ?, updated_at = ? WHERE company_id = ?",
                [self._dump_provenance(provenance), self._utc_now(), company_id],
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_company(company_id)

    def mark_inactive(
        self,
        company_id: str,
        last_active_on: date,
        provenance: CompanyProvenance,
    ) -> CompanyIdentity:
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self._require_company(company_id)
            active_rows = self.connection.execute(
                "SELECT security_id, valid_from FROM company_security_mappings WHERE company_id = ? AND status = 'active'",
                [company_id],
            ).fetchall()
            for security_id, valid_from in active_rows:
                if last_active_on < valid_from:
                    raise ValueError("The last active date cannot precede a security mapping.")
                self.connection.execute(
                    """UPDATE company_security_mappings
                       SET valid_to = ?, status = 'inactive', updated_at = ? WHERE security_id = ?""",
                    [last_active_on, self._utc_now(), security_id],
                )
            self.connection.execute(
                "UPDATE companies SET status = 'inactive', provenance = ?, updated_at = ? WHERE company_id = ?",
                [self._dump_provenance(provenance), self._utc_now(), company_id],
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        return self.get_company(company_id)

    def resolve_ticker(
        self,
        ticker: str,
        as_of: date | None = None,
        include_historical: bool = True,
    ) -> CompanyIdentity | None:
        normalized_ticker = normalize_ticker(ticker)
        if as_of is not None:
            row = self.connection.execute(
                """SELECT company_id FROM company_security_mappings
                   WHERE ticker = ? AND valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?)
                   ORDER BY is_primary DESC, valid_from DESC LIMIT 1""",
                [normalized_ticker, as_of, as_of],
            ).fetchone()
        else:
            row = self.connection.execute(
                """SELECT company_id FROM company_security_mappings
                   WHERE ticker = ? AND status = 'active'
                   ORDER BY is_primary DESC, valid_from DESC LIMIT 1""",
                [normalized_ticker],
            ).fetchone()
            if row is None and include_historical:
                row = self.connection.execute(
                    """SELECT company_id FROM company_security_mappings
                       WHERE ticker = ? ORDER BY coalesce(valid_to, DATE '9999-12-31') DESC, valid_from DESC LIMIT 1""",
                    [normalized_ticker],
                ).fetchone()
        return self.get_company(row[0]) if row else None

    def resolve_cik(self, cik: str | int) -> CompanyIdentity | None:
        row = self.connection.execute(
            "SELECT company_id FROM companies WHERE cik = ?",
            [normalize_cik(cik)],
        ).fetchone()
        return self.get_company(row[0]) if row else None

    def get_company(self, company_id: str) -> CompanyIdentity:
        row = self.connection.execute(
            """SELECT company_id, cik, legal_name, sector, industry, fiscal_year_end, status, provenance,
                      created_at, updated_at
               FROM companies WHERE company_id = ?""",
            [company_id],
        ).fetchone()
        if row is None:
            raise KeyError(f"Company {company_id} does not exist.")
        securities = self._security_mappings(company_id)
        current_primary = next(
            (mapping for mapping in reversed(securities) if mapping.is_primary and mapping.status == CompanyStatus.ACTIVE),
            None,
        )
        latest_primary = current_primary or next(
            (mapping for mapping in reversed(securities) if mapping.is_primary),
            None,
        )
        return CompanyIdentity(
            company_id=row[0],
            cik=row[1],
            legal_name=row[2],
            primary_ticker=latest_primary.ticker if latest_primary else None,
            exchange=latest_primary.exchange if latest_primary else None,
            sector=row[3],
            industry=row[4],
            fiscal_year_end=row[5],
            status=row[6],
            provenance=self._load_provenance(row[7]),
            securities=securities,
            created_at=self._aware(row[8]),
            updated_at=self._aware(row[9]),
        )

    def count_companies(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM companies").fetchone()[0])

    def count_securities(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM company_security_mappings").fetchone()[0])

    def _register_security(
        self,
        company_id: str,
        ticker: str,
        exchange: str | None,
        effective_from: date,
        is_primary: bool,
        provenance: CompanyProvenance,
    ) -> str:
        owner = self._active_ticker_owner(ticker)
        if owner and owner[0] != company_id:
            raise IdentityConflictError(f"Ticker {ticker} is already assigned to another company.")
        existing = self.connection.execute(
            """SELECT security_id, is_primary FROM company_security_mappings
               WHERE company_id = ? AND ticker = ? AND coalesce(exchange, '') = coalesce(?, '')
                 AND status = 'active' ORDER BY valid_from DESC LIMIT 1""",
            [company_id, ticker, exchange],
        ).fetchone()
        if existing:
            if is_primary and not existing[1] and self._active_primary(company_id) is None:
                self.connection.execute(
                    "UPDATE company_security_mappings SET is_primary = TRUE, provenance = ?, updated_at = ? WHERE security_id = ?",
                    [self._dump_provenance(provenance), self._utc_now(), existing[0]],
                )
            else:
                self._refresh_security(existing[0], provenance)
            return existing[0]
        if is_primary and self._active_primary(company_id) is not None:
            raise IdentityConflictError("Use change_primary_ticker to preserve the earlier primary mapping.")
        security_id = str(uuid4())
        now = self._utc_now()
        self.connection.execute(
            """INSERT INTO company_security_mappings
               (security_id, company_id, ticker, exchange, valid_from, valid_to, is_primary, status,
                provenance, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, NULL, ?, 'active', ?, ?, ?)""",
            [
                security_id,
                company_id,
                ticker,
                exchange,
                effective_from,
                is_primary,
                self._dump_provenance(provenance),
                now,
                now,
            ],
        )
        return security_id

    def _security_mappings(self, company_id: str) -> list[SecurityMapping]:
        rows = self.connection.execute(
            """SELECT security_id, company_id, ticker, exchange, valid_from, valid_to, is_primary, status,
                      provenance, created_at, updated_at
               FROM company_security_mappings WHERE company_id = ?
               ORDER BY valid_from, ticker, exchange""",
            [company_id],
        ).fetchall()
        return [
            SecurityMapping(
                security_id=row[0],
                company_id=row[1],
                ticker=row[2],
                exchange=row[3],
                valid_from=row[4],
                valid_to=row[5],
                is_primary=row[6],
                status=row[7],
                provenance=self._load_provenance(row[8]),
                created_at=self._aware(row[9]),
                updated_at=self._aware(row[10]),
            )
            for row in rows
        ]

    def _active_ticker_owner(self, ticker: str) -> tuple[str, str] | None:
        return self.connection.execute(
            """SELECT company_id, security_id FROM company_security_mappings
               WHERE ticker = ? AND status = 'active' ORDER BY is_primary DESC, valid_from DESC LIMIT 1""",
            [ticker],
        ).fetchone()

    def _active_primary(self, company_id: str) -> tuple[str, str, str | None] | None:
        return self.connection.execute(
            """SELECT security_id, ticker, exchange FROM company_security_mappings
               WHERE company_id = ? AND status = 'active' AND is_primary = TRUE
               ORDER BY valid_from DESC LIMIT 1""",
            [company_id],
        ).fetchone()

    def _refresh_security(self, security_id: str, provenance: CompanyProvenance) -> None:
        self.connection.execute(
            "UPDATE company_security_mappings SET provenance = ?, updated_at = ? WHERE security_id = ?",
            [self._dump_provenance(provenance), self._utc_now(), security_id],
        )

    def _require_company(self, company_id: str) -> None:
        if self.connection.execute("SELECT 1 FROM companies WHERE company_id = ?", [company_id]).fetchone() is None:
            raise KeyError(f"Company {company_id} does not exist.")

    @staticmethod
    def _dump_provenance(provenance: CompanyProvenance) -> str:
        return json.dumps(provenance.model_dump(mode="json"))

    @staticmethod
    def _load_provenance(payload: str) -> CompanyProvenance:
        return CompanyProvenance.model_validate(json.loads(payload))

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
