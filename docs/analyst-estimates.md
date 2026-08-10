# Analyst Estimates Provider Contract

Sources: `src/gbb_terminal/intelligence/estimate_models.py`, `estimates.py`, and `src/gbb_terminal/market_data/providers/estimates.py`

INT-08 defines a provider-neutral boundary for analyst expectations without selecting, scraping, or purchasing a commercial data source. Company Intelligence remains useful when this provider returns no coverage.

## Reported Facts Versus Expectations

- SEC Company Facts and normalized financial metrics are reported evidence.
- Analyst estimates are third-party or manually entered expectations.
- An estimate never becomes a reported fact and never changes normalized SEC history.
- Every observation carries provider identity, `observed_at`, and `known_at`.
- Multiple observations for the same fiscal period are retained as revision history and filtered by the requested as-of boundary.

The V3 response exposes this distinction directly in provenance. No estimate-derived recommendation or forward valuation is produced in Release 0.8.

## Normalized Observation

`EstimateObservation` supports:

- Revenue consensus in `USD`.
- Diluted EPS consensus in `USD/share`.
- Fiscal year, `FY|Q1|Q2|Q3|Q4`, and exact period end.
- Mean and/or median, optional high/low, and estimate count.
- Observation timestamp, publication-aware `known_at`, provider identity, source metadata, and contract version.

Unknown fields are rejected. Timestamps must include a timezone. At least mean or median is required. Revenue/EPS units are explicit so a fixture cannot silently mix USD and USD millions.

## Provider Interface

`EstimateProvider` is a runtime-checkable protocol with:

```python
def estimates(company: CompanyIdentity, as_of: datetime) -> list[EstimateObservation]: ...
def status() -> dict: ...
```

Domain and API code does not import a vendor SDK. A future licensed adapter can implement the same protocol without changing Company Intelligence calculations.

`ManualEstimateProvider` reads optional local `conf/estimates.json`. That file is ignored by Git. Select a different path through `paths.estimate_fixture_path` or `GBB_ESTIMATE_FIXTURE_PATH`.

Example fixture:

```json
{
  "observations": [
    {
      "provider_key": "manual_research",
      "provider_name": "Manual Research Fixture",
      "symbol": "NVDA",
      "cik": "0001045810",
      "metric": "revenue",
      "fiscal_year": 2027,
      "fiscal_period": "Q1",
      "period_end": "2026-04-26",
      "unit": "USD",
      "mean": 50000000000,
      "median": 49800000000,
      "high": 52000000000,
      "low": 47000000000,
      "estimate_count": 24,
      "observed_at": "2026-04-01T20:00:00Z",
      "known_at": "2026-04-01T20:00:00Z",
      "source_metadata": {"note": "Local development fixture"}
    }
  ]
}
```

If `estimate_id` is omitted, the manual adapter derives a stable hash from provider, company/security, metric, fiscal period, period end, and `known_at`.

## Fiscal-Period Mapping

An estimate matches a reported result only when all of the following agree:

- Metric identity.
- Exact period end.
- Fiscal year.
- Fiscal period label.

`FY` maps to annual normalized metrics; quarters map to discrete-quarterly metrics. A shared period end with conflicting fiscal labels returns `period_mismatch`. An exact period not yet reported inside `as_of` returns `unreported`. A matched comparison includes reported source fact IDs, absolute difference, and surprise percentage when consensus is non-zero.

## API

`GET /api/v3/companies/{ticker}/estimates` accepts optional comma-separated `metrics=revenue,diluted_eps` and timezone-aware `as_of`. With no configured fixture/provider, it returns `200`, an empty comparison list, provider status, and a visible no-coverage warning.

No source is scraped by this implementation. Users must only import data they are entitled to reuse.
