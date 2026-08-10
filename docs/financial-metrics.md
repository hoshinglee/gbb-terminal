# Normalized Financial Metrics

Sources:

- `src/gbb_terminal/intelligence/metric_definitions.py`
- `src/gbb_terminal/intelligence/metrics.py`
- `src/gbb_terminal/intelligence/metric_models.py`

The normalized metrics engine converts point-in-time SEC/XBRL observations into deterministic company research metrics. Provider extraction remains separate: SEC supplies source facts, while the intelligence domain owns concept precedence, units, period construction, derivations, warnings, and lineage.

## Versioned Definitions

Every result carries `definition_version`. Version `1.0.0` centralizes ordered SEC concept candidates for:

| Metric | Preferred concept direction | Normalized unit |
| --- | --- | --- |
| Revenue | Contract revenue → revenues → net sales | USD |
| Gross profit | Gross profit | USD |
| Operating income | Operating income/loss | USD |
| Net income | Net income/loss → profit/loss | USD |
| Diluted EPS | Diluted EPS concepts | USD/share |
| Operating cash flow | Operating cash-flow concepts | USD |
| Capital expenditure | Property/plant/equipment payment concepts | USD positive outflow |
| Cash | Cash and equivalents → broader cash/restricted cash | USD |
| Debt | Direct total-debt concepts, then deterministic current/noncurrent component groups | USD |
| Diluted shares | Diluted weighted-average shares → visible basic-share fallback | shares |

Hidden supporting definitions cover stockholders' equity, pretax income, and income-tax expense for ROE and ROIC. The engine uses the first supported concept with a compatible unit. Lower-precedence concepts never override a preferred valid observation merely because they were fetched later.

## Unit Rules

Unit conversion is explicit and never performs currency conversion:

- `USD`, `USDm`, and `USDth` normalize to USD.
- `shares`, `sharesm`, and `shares_thousands` normalize to shares.
- `USD/shares` and `USD/share` normalize to USD/share.
- Unsupported units, including non-USD currencies, produce a missing value plus a warning.
- Capital-expenditure payment facts normalize to a positive outflow before FCF calculation.

## Period Views

- **Annual:** duration facts of at least 250 days associated with FY/10-K reporting, plus matching instant balances.
- **Quarterly:** discrete duration facts between 60 and 120 days associated with quarterly frames/10-Q reporting, plus matching instant balances. Year-to-date durations are not silently treated as standalone quarters.
- **TTM:** rolling groups of four contiguous discrete quarters. Flow and per-share metrics are summed, diluted shares are averaged, and instant balances use the latest quarter.

When four discrete quarters are unavailable, TTM remains unavailable with a visible warning. The engine does not invent a missing quarter from unrelated periods.

## Derived Metrics

| Metric | Definition |
| --- | --- |
| Free cash flow | Operating cash flow − capital expenditure |
| Revenue / EPS growth | Annual year-over-year; quarterly and TTM compare with the period four quarters earlier |
| Gross / operating / FCF margin | Numerator ÷ revenue |
| ROE | Net income ÷ average comparable stockholders' equity; quarterly numerator is annualized |
| ROIC | NOPAT proxy ÷ average debt + equity − cash, using bounded effective tax rate; quarterly numerator is annualized |
| Net debt | Debt − cash |
| Share dilution | Diluted-share growth against the comparable period |

If required inputs are absent, zero, incompatible, or ambiguous, the derived value is `null` and its warning explains why. Ending balance is used only when a prior comparable balance is unavailable, and that assumption is disclosed.

## Point-In-Time And Lineage

`NormalizedMetricsService.calculate()` passes its timezone-aware `as_of` boundary into the fact repository. Later filings and restatements therefore cannot enter an earlier result. Every non-null metric lists the exact `source_fact_ids` used; derived metrics contain the union of their source inputs. The frontend/API never needs to infer lineage from labels.

## Function Definitions

- `UnitNormalizer.normalize(value, source_unit, target_unit)`: validates and scales a source unit without currency conversion.
- `NormalizedMetricsService.calculate(ticker_or_cik, period_kind, as_of)`: resolves canonical identity, loads only supported source concepts under the as-of boundary, constructs periods, and returns typed normalized metrics.
- `MetricPeriodKind`: `annual`, `quarterly`, or `ttm`.
- `NormalizedMetric`: value/unit/period/definition version, derivation flag, source fact IDs, and warnings.
- `NormalizedMetricSet`: canonical company context, requested period view, as-of timestamp, result metrics, and set-level warnings.
