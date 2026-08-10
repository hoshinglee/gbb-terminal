from xml.etree import ElementTree

import pandas as pd
import pytest

from gbb_terminal.market_data.providers.sec import SECProvider
from gbb_terminal.market_data.providers.yahoo import YahooProvider


def test_sec_field_reads_direct_and_nested_values():
    root = ElementTree.fromstring("""
        <ownershipDocument>
          <issuer><issuerName>Example Corp</issuerName></issuer>
          <transaction>
            <transactionShares><value>1250</value></transactionShares>
          </transaction>
        </ownershipDocument>
    """)
    assert SECProvider._field(root, "issuerName") == "Example Corp"
    assert SECProvider._field(root, "transactionShares") == "1250"
    assert SECProvider._field(root, "missing") is None


def test_sec_number_handles_missing_and_invalid_values():
    assert SECProvider._number("12.5") == 12.5
    assert SECProvider._number(None) is None
    assert SECProvider._number("not-a-number") is None


def test_sec_company_ticker_directory_parser_uses_named_fields():
    payload = {
        "fields": ["name", "exchange", "ticker", "cik"],
        "data": [
            ["NVIDIA CORP", "Nasdaq", "NVDA", 1045810],
            ["Missing Ticker", "NYSE", "", 1234],
        ],
    }

    assert SECProvider.company_ticker_rows(payload) == [
        {"cik": 1045810, "legalName": "NVIDIA CORP", "ticker": "NVDA", "exchange": "Nasdaq"}
    ]


def test_sec_company_ticker_directory_rejects_unknown_shape():
    with pytest.raises(ValueError, match="expected fields"):
        SECProvider.company_ticker_rows({"fields": ["name", "ticker"], "data": []})


def test_sec_acceptance_times_are_keyed_by_accession():
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0001-24-000001", "0001-24-000002"],
                "acceptanceDateTime": ["2024-02-01T20:30:00Z", ""],
            }
        }
    }

    result = SECProvider.acceptance_times(payload)

    assert result["0001-24-000001"].isoformat() == "2024-02-01T20:30:00+00:00"
    assert "0001-24-000002" not in result


def test_yahoo_option_chain_uses_requested_expiry_and_keeps_all_contracts(monkeypatch):
    calls = pd.DataFrame([
        {"contractSymbol": "NVDA261218C00180000", "lastTradeDate": "2026-08-08T15:30:00Z", "strike": 180, "lastPrice": 12, "bid": 11.8, "ask": 12.2, "change": 0.5, "percentChange": 4.3, "volume": 120, "openInterest": 1500, "impliedVolatility": 0.32, "inTheMoney": True, "currency": "USD"},
        {"contractSymbol": "NVDA261218C00200000", "lastTradeDate": "2026-08-08T15:31:00Z", "strike": 200, "lastPrice": 7, "bid": 6.8, "ask": 7.2, "change": -0.2, "percentChange": -2.7, "volume": 80, "openInterest": 900, "impliedVolatility": 0.35, "inTheMoney": False, "currency": "USD"},
    ])
    puts = calls.assign(contractSymbol=["NVDA261218P00180000", "NVDA261218P00200000"])

    class FakeTicker:
        options = ("2026-09-18", "2026-12-18")

        def option_chain(self, expiration):
            assert expiration == "2026-12-18"
            return type("Chain", (), {"calls": calls, "puts": puts})()

    monkeypatch.setattr("gbb_terminal.market_data.providers.yahoo.yf.Ticker", lambda _: FakeTicker())
    payload = YahooProvider().option_chain("NVDA", "2026-12-18").data

    assert payload["expiration"] == "2026-12-18"
    assert payload["defaultExpiration"] == "2026-09-18"
    assert len(payload["calls"]) == 2
    assert payload["calls"][0]["mid"] == 12
    assert payload["calls"][0]["spread"] == 0.4
    assert payload["calls"][0]["quoteQuality"] == "Two-Sided"
