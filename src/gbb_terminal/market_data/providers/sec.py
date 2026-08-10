from __future__ import annotations

from datetime import datetime, timezone
from xml.etree import ElementTree

from ..models import DataEnvelope
from .base import BaseProvider


class SECProvider(BaseProvider):
    name = "SEC EDGAR"

    def company_tickers(self) -> DataEnvelope[list[dict]]:
        payload = self.request_json("https://www.sec.gov/files/company_tickers_exchange.json")
        retrieved_at = datetime.now(timezone.utc)
        return DataEnvelope(
            "sec_company_tickers",
            "US",
            self.company_ticker_rows(payload),
            retrieved_at,
            retrieved_at,
            retrieved_at,
            self.delayed_status,
            self.name,
            [
                "SEC ticker, CIK, and exchange associations are periodically updated and do not guarantee accuracy, scope, or historical effective dates."
            ],
        )

    def submissions(self, cik: str) -> DataEnvelope[dict]:
        normalized = "".join(character for character in cik if character.isdigit()).zfill(10)
        payload = self.request_json(f"https://data.sec.gov/submissions/CIK{normalized}.json")
        retrieved_at = datetime.now(timezone.utc)
        recent = payload.get("filings", {}).get("recent", {})
        accepted = recent.get("acceptanceDateTime", [])
        known_at = datetime.fromisoformat(accepted[0].replace("Z", "+00:00")) if accepted else retrieved_at
        return DataEnvelope("sec_submissions", normalized, payload, known_at, known_at, retrieved_at, self.delayed_status, self.name, ["Filings become usable only at SEC acceptance time; report-period dates are not publication dates."])

    def company_facts(self, cik: str) -> DataEnvelope[dict]:
        normalized = "".join(character for character in cik if character.isdigit()).zfill(10)
        payload = self.request_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized}.json")
        retrieved_at = datetime.now(timezone.utc)
        return DataEnvelope("sec_company_facts", normalized, payload, retrieved_at, retrieved_at, retrieved_at, self.delayed_status, self.name, ["Company facts may be amended; historical research must join facts to filing acceptance timestamps."])

    def thirteen_f_holdings(self, cik: str, accession: str) -> DataEnvelope[list[dict]]:
        normalized, base = self._filing_base(cik, accession)
        index = self.request_json(f"{base}/index.json")
        items = index.get("directory", {}).get("item", [])
        candidates = [item["name"] for item in items if item.get("name", "").lower().endswith((".xml", ".txt")) and any(token in item.get("name", "").lower() for token in ("info", "table"))]
        if not candidates:
            raise ValueError("The filing index does not expose a 13F information-table document.")
        root = ElementTree.fromstring(self.request_bytes(f"{base}/{candidates[0]}"))
        holdings = []
        for table in [element for element in root.iter() if self._local_name(element.tag) == "infoTable"]:
            holdings.append({"issuer": self._field(table, "nameOfIssuer"), "classTitle": self._field(table, "titleOfClass"), "cusip": self._field(table, "cusip"), "valueThousands": self._number(self._field(table, "value")), "shares": self._number(self._field(table, "sshPrnamt")), "shareType": self._field(table, "sshPrnamtType"), "discretion": self._field(table, "investmentDiscretion")})
        retrieved_at = datetime.now(timezone.utc)
        known_at = self._filing_known_at(normalized, accession) or retrieved_at
        return DataEnvelope("sec_13f_holdings", normalized, holdings, known_at, known_at, retrieved_at, self.delayed_status, self.name, ["Holdings become known at filing acceptance, which may be up to 45 days after quarter end."])

    def form4_transactions(self, cik: str, accession: str, document: str) -> DataEnvelope[dict]:
        normalized, base = self._filing_base(cik, accession)
        root = ElementTree.fromstring(self.request_bytes(f"{base}/{document}"))
        transactions = []
        for transaction in [element for element in root.iter() if self._local_name(element.tag) in {"nonDerivativeTransaction", "derivativeTransaction"}]:
            transactions.append({"securityTitle": self._field(transaction, "securityTitle"), "transactionDate": self._field(transaction, "transactionDate"), "transactionCode": self._field(transaction, "transactionCode"), "shares": self._number(self._field(transaction, "transactionShares")), "price": self._number(self._field(transaction, "transactionPricePerShare")), "acquiredDisposed": self._field(transaction, "transactionAcquiredDisposedCode"), "sharesOwnedAfter": self._number(self._field(transaction, "sharesOwnedFollowingTransaction"))})
        retrieved_at = datetime.now(timezone.utc)
        known_at = self._filing_known_at(normalized, accession) or retrieved_at
        return DataEnvelope("sec_form4_transactions", normalized, {"issuer": self._field(root, "issuerName"), "reportingOwner": self._field(root, "rptOwnerName"), "transactions": transactions}, known_at, known_at, retrieved_at, self.delayed_status, self.name, ["Transactions become known at SEC filing acceptance, not their transaction date."])

    @staticmethod
    def recent_forms(payload: dict, forms: set[str]) -> list[dict]:
        recent = payload.get("filings", {}).get("recent", {})
        keys = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument")
        rows = [dict(zip(keys, values)) for values in zip(*(recent.get(key, []) for key in keys))]
        return [row for row in rows if row["form"] in forms]

    @staticmethod
    def company_ticker_rows(payload: dict) -> list[dict]:
        fields = payload.get("fields", [])
        required = {"cik", "name", "ticker", "exchange"}
        if not required.issubset(fields):
            raise ValueError("The SEC company-ticker directory does not contain its expected fields.")
        indexes = {field: fields.index(field) for field in required}
        rows = []
        for values in payload.get("data", []):
            if not isinstance(values, list) or len(values) < len(fields):
                continue
            ticker = values[indexes["ticker"]]
            name = values[indexes["name"]]
            cik = values[indexes["cik"]]
            if ticker and name and cik is not None:
                rows.append(
                    {
                        "cik": cik,
                        "legalName": name,
                        "ticker": ticker,
                        "exchange": values[indexes["exchange"]] or None,
                    }
                )
        return rows

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _number(value: str | None) -> float | None:
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    @classmethod
    def _field(cls, root, field_name: str) -> str | None:
        element = next((item for item in root.iter() if cls._local_name(item.tag) == field_name), None)
        if element is None:
            return None
        direct = (element.text or "").strip()
        if direct:
            return direct
        value = next((item for item in element.iter() if cls._local_name(item.tag) == "value" and (item.text or "").strip()), None)
        return (value.text or "").strip() if value is not None else None

    def _filing_known_at(self, cik: str, accession: str) -> datetime | None:
        payload = self.submissions(cik).data
        recent = payload.get("filings", {}).get("recent", {})
        for number, accepted in zip(recent.get("accessionNumber", []), recent.get("acceptanceDateTime", [])):
            if number == accession and accepted:
                return datetime.fromisoformat(accepted.replace("Z", "+00:00"))
        return None

    @staticmethod
    def _filing_base(cik: str, accession: str) -> tuple[str, str]:
        normalized = "".join(character for character in cik if character.isdigit()).zfill(10)
        accession_path = accession.replace("-", "")
        return normalized, f"https://www.sec.gov/Archives/edgar/data/{int(normalized)}/{accession_path}"
