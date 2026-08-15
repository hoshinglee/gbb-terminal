# Segment, Geography, And KPI Intelligence

Sources: `src/gbb_terminal/intelligence/operations_models.py`, `src/gbb_terminal/intelligence/operations_repository.py`, `src/gbb_terminal/intelligence/operations.py`, and `app/web/src/features/company-intelligence/operations-intelligence.tsx`

Operating Intelligence preserves how a company describes its business over time. It supports issuer-defined reportable segments, exact geographic groupings, and typed company-specific KPIs without forcing incompatible companies or historical definitions into one standardized series.

## Business Definitions

| Concept | Definition |
| --- | --- |
| Metric definition | Versioned category, key, label, measure, unit, value type, reporting basis, validity, and source evidence. |
| Segment | An issuer-reported reportable business component. It is not silently inferred from products or sectors. |
| Geography | The issuer's exact disclosed grouping, such as `Americas Including United States`; GBB does not relabel it as a standard region. |
| KPI | A flexible typed company measure such as subscribers, utilization, units, backlog, or capacity. |
| Reporting basis | The set of definitions and accounting presentation under which values are compatible. |
| Definition transition | An explicit `supersedes_definition_id` link representing reorganization, relabeling, or basis change. |

## Versioning Rules

- A changed label, measure, unit, value type, or reporting basis requires a new definition linked to the prior definition.
- Earlier definitions and observations remain immutable.
- Every definition and observation requires inspectable evidence owned by the same canonical company.
- Definition and observation `known_at` timestamps cannot precede source availability.
- An observation unit must equal the definition unit.
- Repeated retrieval of the same canonical observation deduplicates rather than appending noise.

## Calculations

`OperationsIntelligenceService.history()` calculates two navigation aids:

- **Growth:** calculated only between periods inside the same definition version. The first point of a new definition has no growth value.
- **Mix:** calculated only among segment or geography observations sharing category, reporting basis, measure, unit, and period end.

These restrictions prevent a reorganization, changed geography basis, or different metric unit from producing a false growth rate or total. Missing values remain missing and are not treated as zero.

## API And UI

`GET /api/v3/companies/{ticker}/operations` accepts optional comma-separated `categories` and a timezone-aware `as_of`. It returns definition evidence, point evidence, transitions, calculated compatible mix/growth, and explicit coverage warnings.

The React Operations view shows:

- latest segment and geography mix bars;
- complete historical values with period, unit, `known_at`, definition version, and reporting basis;
- separate definition and observation evidence controls;
- typed custom KPI history;
- visible reorganization warnings and definition transitions;
- explicit empty states for each missing category.

## Limitations

- Public reporting depth varies by issuer and period.
- KPIs are intentionally not assumed comparable across companies.
- A disclosed segment value may use revenue, profit, assets, or another measure; only equal measures and units are combined.
- Curated depth is preferable to false universal coverage.
