from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from html.parser import HTMLParser

from ..market_data.providers.base import BaseProvider, ProviderUnavailable
from .models import UniverseConstituent, UniverseKey, UniverseSourceSnapshot


class UniverseProvider(ABC):
    @abstractmethod
    def fetch_snapshot(self, universe_key: UniverseKey) -> UniverseSourceSnapshot:
        raise NotImplementedError


class _ConstituentTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "constituents":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag in {"th", "td"}:
            self.in_cell = True
            self.current_cell = []
        elif self.in_cell and tag == "br":
            self.current_cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"th", "td"}:
            value = re.sub(r"\s+", " ", "".join(self.current_cell)).strip()
            self.current_row.append(re.sub(r"\[\d+\]$", "", value).strip())
            self.in_cell = False
        elif self.in_row and tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_row = False
        elif self.in_table and tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


class WikipediaSP500Provider(BaseProvider, UniverseProvider):
    name = "Wikipedia"
    delayed_status = "Current Composition Snapshot"
    minimum_interval_seconds = 1.0
    source_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def fetch_snapshot(self, universe_key: UniverseKey) -> UniverseSourceSnapshot:
        if universe_key != UniverseKey.SP500:
            raise ValueError(f"{self.name} does not support universe {universe_key.value}.")
        content = self.request_bytes(self.source_url)
        parser = _ConstituentTableParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        if len(parser.rows) < 2:
            raise ProviderUnavailable("The S&P 500 constituent table was not found in the public source.")
        headers = parser.rows[0]
        required = {"Symbol", "Security", "GICS Sector", "GICS Sub-Industry", "CIK"}
        if not required.issubset(headers):
            raise ProviderUnavailable("The public S&P 500 constituent table has an unsupported schema.")
        constituents = []
        for row in parser.rows[1:]:
            if len(row) < len(headers):
                continue
            values = dict(zip(headers, row, strict=False))
            source_symbol = values["Symbol"].strip().upper()
            symbol = source_symbol.replace(".", "-")
            try:
                added = date.fromisoformat(values.get("Date added", "")) if values.get("Date added") else None
                constituent = UniverseConstituent(
                    symbol=symbol,
                    source_symbol=source_symbol,
                    company_name=values["Security"],
                    sector=values["GICS Sector"],
                    sub_industry=values["GICS Sub-Industry"],
                    cik=values["CIK"],
                    date_added=added,
                    metadata={"headquarters": values.get("Headquarters Location"), "founded": values.get("Founded")},
                )
            except ValueError:
                continue
            constituents.append(constituent)
        if len(constituents) < 400:
            raise ProviderUnavailable(f"Only {len(constituents)} valid S&P 500 constituents were parsed; refusing an incomplete snapshot.")
        constituents.sort(key=lambda item: item.symbol)
        canonical = [item.model_dump(mode="json") for item in constituents]
        content_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        now = datetime.now(timezone.utc)
        return UniverseSourceSnapshot(
            universe_key=universe_key,
            as_of_date=now.date(),
            source=self.name,
            source_url=self.source_url,
            known_at=now,
            retrieved_at=now,
            content_hash=content_hash,
            constituents=constituents,
            quality_warnings=[
                "This is a current public composition snapshot, not a licensed historical S&P index-membership feed.",
                "Constituent additions and removals become known only when the source snapshot is retrieved.",
            ],
            metadata={"providerStatus": self.delayed_status},
        )
