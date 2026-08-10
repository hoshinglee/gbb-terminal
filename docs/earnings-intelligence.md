# Earnings Events And Reaction Analytics

Sources: `src/gbb_terminal/intelligence/earnings.py`, `earnings_models.py`, and `earnings_repository.py`

Earnings Intelligence models a reported fiscal period as an explicit, source-backed event and measures what the security did around that event. The initial free-data implementation uses SEC filing acceptance as timing evidence. A company may publish a separate earnings release earlier, so every result displays that limitation.

## Event Identity And Evidence

An event has a stable identity derived from canonical `company_id`, fiscal period end, and fiscal period. Re-downloading the same SEC data updates the same event row. Amendments do not create a second market event for the same fiscal period.

Each event retains:

- Canonical company, CIK, and current security ticker.
- Fiscal year/period and economic period end.
- Exact SEC acceptance timestamp when available, otherwise filed date only.
- Before-open, after-close, intraday, or unknown timing classification in `America/New_York`.
- Accession number, form, SEC filing URL, `known_at`, and source fact IDs.
- Normalized reported revenue, diluted EPS, net income, gross margin, and operating margin when supported.
- Explicit warnings when release timing, guidance, or consensus data are unavailable.

## Trading-Session Alignment

- Before-open events anchor to the same observed trading session.
- After-close events anchor to the next observed trading session.
- Weekend and market-holiday dates anchor to the next actual price row, not calendar-day arithmetic.
- Intraday events anchor to the same session and warn that D0 includes movement before the timestamp.
- Date-only events use the first session on or after the filed date and remain quality-warning state.

The session immediately before the anchor is the common return baseline. D0, D+1, D+5, D+20, and D+60 are cumulative close-to-close returns from that baseline to the named forward session. Opening gap uses anchor open versus prior close. Benchmark-adjusted return subtracts the selected benchmark's return over the exact same session dates.

Abnormal volume is anchor-session volume divided by the median of up to 20 prior observed sessions, requiring at least five observations. Volume percentile ranks anchor volume against up to 60 prior sessions.

## Aggregates

The history response reports median absolute D0 move, positive D0 frequency, median D+5 and D+20 drift, the historical D0 range, and included/excluded sample counts. Events lacking the required sessions are excluded rather than filled with zero. Historical reaction is descriptive evidence and must not be presented as a prediction of the next event.

## Storage And API

DuckDB schema version 9 adds `earnings_events` and `earnings_reactions`. Events preserve source evidence and normalized facts. Reactions are keyed by event, benchmark, and engine version so they can be recomputed deterministically without erasing prior engine semantics.

`GET /api/v3/companies/{ticker}/earnings` accepts an optional benchmark, timezone-aware `as_of`, and event limit. The strict V3 response includes event evidence, reported metrics, complete reaction windows/path, volume context, aggregate sample size, versions, provenance, and caveats.
