from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter

from ...market_data.service import MarketData
from .shared import bad_request


def create_market_router(data: MarketData) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Market Data"])

    @router.get("/data-providers")
    async def providers():
        return {"providers": data.provider_statuses()}

    @router.get("/market-overview")
    async def market_overview():
        try:
            payload = await data.dashboard()
            return {**payload, "providers": data.provider_statuses(), "generatedAt": datetime.now(timezone.utc).isoformat()}
        except ValueError as error:
            raise bad_request(error) from error

    async def public_payload(dataset: str, symbol: str, loader, transform=lambda value: value) -> dict[str, Any]:
        try:
            envelope = await asyncio.to_thread(loader)
            payload = transform(envelope.data)
            metadata = envelope.metadata()
            data.store.save_provider_payload(metadata, payload)
            return {"metadata": metadata, "data": payload}
        except ValueError as error:
            for provider in data.providers:
                cached = data.store.load_provider_payload(provider.name, dataset, symbol)
                if cached:
                    cached["metadata"]["status"] = "Stale Cache"
                    cached["metadata"]["qualityWarnings"] = [*cached["metadata"].get("qualityWarnings", []), str(error)]
                    return cached
            raise bad_request(error) from error

    @router.get("/public-data/sec/{cik}/filings")
    async def sec_filings(cik: str, forms: str = "13F-HR,4,10-K,10-Q"):
        requested = {form.strip().upper() for form in forms.split(",") if form.strip()}
        return await public_payload("sec_submissions", cik.zfill(10), lambda: data.sec.submissions(cik), lambda payload: data.sec.recent_forms(payload, requested))

    @router.get("/public-data/sec/{cik}/fundamentals")
    async def sec_fundamentals(cik: str, concepts: str = "Assets,Liabilities,Revenues,NetIncomeLoss"):
        requested = [concept.strip() for concept in concepts.split(",") if concept.strip()]

        def latest(payload: dict) -> dict:
            facts = payload.get("facts", {}).get("us-gaap", {})
            result = {}
            for concept in requested:
                fact = facts.get(concept, {})
                observations = [observation for values in fact.get("units", {}).values() for observation in values]
                if observations:
                    result[concept] = max(observations, key=lambda item: (item.get("filed", ""), item.get("end", "")))
            return result

        return await public_payload("sec_company_facts", cik.zfill(10), lambda: data.sec.company_facts(cik), latest)

    @router.get("/public-data/sec/{cik}/13f/{accession}")
    async def sec_13f(cik: str, accession: str):
        return await public_payload("sec_13f_holdings", cik.zfill(10), lambda: data.sec.thirteen_f_holdings(cik, accession))

    @router.get("/public-data/sec/{cik}/form4/{accession}/{document}")
    async def sec_form4(cik: str, accession: str, document: str):
        return await public_payload("sec_form4_transactions", cik.zfill(10), lambda: data.sec.form4_transactions(cik, accession, document))

    @router.get("/public-data/finra/short-sale-volume/{trade_date}")
    async def finra_short_volume(trade_date: date, symbol: str | None = None):
        transform = (lambda rows: [row for row in rows if row.get("Symbol", "").upper() == symbol.upper()]) if symbol else (lambda rows: rows)
        return await public_payload("daily_short_sale_volume", "US", lambda: data.finra.short_sale_volume(trade_date), transform)

    @router.get("/public-data/fred/{series_id}")
    async def fred_series(series_id: str, observations: int = 120):
        def rows(frame: pd.DataFrame) -> list[dict]:
            return [{"date": row.DATE.strftime("%Y-%m-%d"), "value": None if pd.isna(row[series_id.upper()]) else float(row[series_id.upper()])} for _, row in frame.tail(max(1, min(observations, 1000))).iterrows()]

        return await public_payload("macro_series", series_id.upper(), lambda: data.fred.series(series_id), rows)

    @router.get("/public-data/occ")
    async def occ_context():
        return await public_payload("aggregate_options_context", "US", data.occ.report_catalogue)

    return router
