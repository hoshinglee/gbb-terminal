from __future__ import annotations

import re


class IdentityConflictError(ValueError):
    pass


_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,14}$")
_FISCAL_YEAR_END_PATTERN = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper().removeprefix("$").replace(".", "-")
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError("Ticker must use 1-15 letters, numbers, or hyphens.")
    return ticker


def normalize_cik(value: str | int) -> str:
    cik = str(value).strip().upper()
    if cik.startswith("CIK"):
        cik = cik[3:].strip()
    cik = cik.replace(" ", "")
    if not cik.isdigit() or len(cik) > 10:
        raise ValueError("CIK must contain at most 10 digits.")
    return cik.zfill(10)


def normalize_exchange(value: str | None) -> str | None:
    if value is None:
        return None
    exchange = " ".join(value.strip().upper().split())
    return exchange or None


def normalize_fiscal_year_end(value: str | None) -> str | None:
    if value is None:
        return None
    fiscal_year_end = value.strip()
    if len(fiscal_year_end) == 4 and fiscal_year_end.isdigit():
        fiscal_year_end = f"{fiscal_year_end[:2]}-{fiscal_year_end[2:]}"
    if not _FISCAL_YEAR_END_PATTERN.fullmatch(fiscal_year_end):
        raise ValueError("Fiscal year end must use MM-DD or MMDD format.")
    return fiscal_year_end
