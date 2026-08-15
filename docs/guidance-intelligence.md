# Guidance And Management Commitments

Sources: `src/gbb_terminal/intelligence/guidance_models.py`, `src/gbb_terminal/intelligence/guidance_repository.py`, `src/gbb_terminal/intelligence/guidance.py`, and `app/web/src/features/company-intelligence/guidance-timeline.tsx`

Guidance Intelligence is an immutable historical record of management's source-backed financial guidance, KPI targets, strategic commitments, and risk constraints. It does not generate a forecast and does not replace original wording with an LLM summary.

## Business Definitions

| Concept | Definition |
| --- | --- |
| Statement | Exact original wording, topic, type, applicable period, publication timing, extraction method, and evidence. |
| Numeric range | Explicit lower and upper bounds plus a unit. |
| Numeric point | Explicit point value with `at_least`, `at_most`, or `approximately` comparison semantics. |
| Qualitative commitment | Original non-numeric wording. Numeric precision may not be added. |
| Revision | A new immutable statement linked through `supersedes_statement_id`. |
| Evaluation | Append-only status observation such as delivered, missed, withdrawn, or superseded. |
| Evaluation method | `rule_based`, `system`, `manual`, or `interpretive`; non-objective assessment is never presented as deterministic. |

## Integrity Rules

- Every statement requires an exact source span containing the persisted statement wording.
- Source evidence belongs to the same canonical company and must be known by the statement's `known_at`.
- Revisions retain statement type, topic, and metric identity, while originals remain unchanged.
- Saving a revision appends a `superseded` evaluation to its predecessor.
- Withdrawals require explicit source evidence and a note.
- Qualitative statements reject numeric bounds, points, units, or automatic numeric outcomes.
- Approximate numeric statements require a documented manual tolerance; the engine does not invent one.
- Rule-based delivery outcomes require a compatible actual value and unit from normalized SEC facts or inspectable evidence.

## Outcome Evaluation

`GuidanceService.evaluate_numeric()` supports deterministic `within_range`, `at_least`, and `at_most` comparisons. `GuidanceService.evaluate_from_metrics()` locates an exact normalized metric for the applicable period, keeps source-fact lineage, and then applies the same rule. Manual or interpretive evaluations require an explanatory note and remain labelled accordingly.

Revision direction is derived from compatible numeric values:

- higher representative value: `raised`;
- lower representative value: `cut`;
- unchanged value: `reaffirmed`;
- incompatible or qualitative revision: `changed`;
- no predecessor: `initial`.

## API And UI

`GET /api/v3/companies/{ticker}/guidance` accepts optional comma-separated statement `types`, status filters, and timezone-aware `as_of`. It returns chronological statements, revision direction, current status, all visible evaluations, source evidence, and coverage warnings.

The React timeline keeps the following visible:

- issue date, `known_at`, revision number, direction, type, and applicable period;
- normalized range or point beside the exact original statement;
- explicit qualitative labels without fabricated precision;
- status and complete evaluation history;
- objective source-fact count and exact outcome evidence when available;
- source dialogs for every persisted statement;
- a visible warning that the record is historical evidence, not a model forecast.

## Limitations

- Companies may omit, narrow, revise, or withdraw guidance.
- A delivered range does not imply business quality or future repeatability.
- A missed commitment may depend on definition changes or extraordinary events that require source review.
- Open commitments are neither predicted successes nor predicted failures.
