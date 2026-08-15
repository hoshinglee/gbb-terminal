# Business Relationship Network

Sources: `src/gbb_terminal/intelligence/relationship_models.py`, `src/gbb_terminal/intelligence/relationship_repository.py`, `src/gbb_terminal/intelligence/relationships.py`, and `app/web/src/features/company-intelligence/relationship-network.tsx`

The Business Relationship Network helps a hobbyist investor inspect publicly disclosed customers, suppliers, manufacturers, distributors, strategic partners, competitors, and concentration exposures. It is an evidence navigator, not a complete supply-chain database or a trading signal.

## Business Definitions

| Concept | Definition |
| --- | --- |
| Economic edge | Stable relationship identity based on the disclosing `company_id`, normalized counterparty name, relationship type, and direction. |
| Observation | A point-in-time statement about resolution, exposure, confidence, or validity for an economic edge. |
| Resolved counterparty | A disclosed name that maps unambiguously to a canonical company record. |
| Unresolved counterparty | A raw disclosed name such as `Customer A` or an entity that cannot be mapped safely. The application preserves the name and does not guess. |
| Perspective direction | Upstream, downstream, two-way, or market direction as viewed from the selected company. Incoming edges reverse upstream/downstream for display. |
| Confidence | `disclosed`, `strongly_inferred`, or `inferred`. Deterministic explicit-text extraction uses `disclosed`; other labels must remain visible. |
| Validity | Optional effective dates for the economic relationship, separate from when the source became known. |

## Persistence And Identity

- `business_relationships` stores one stable economic edge.
- `relationship_observations` stores append-only point-in-time observations.
- Exact duplicate observations reuse the same deterministic identifier.
- Additional source spans link to the existing observation instead of creating duplicate edges.
- A later observation may supersede an earlier observation without deleting it.
- Human corrections are stored as `human_override`, require evidence and a correction note, and remain visible in history.
- Relationship `known_at` cannot precede the linked source document's `known_at`.

Counterparty normalization removes punctuation and common legal suffixes only for identity matching. The original disclosed name remains available for display and evidence review.

## Deterministic Extraction

`RelationshipExtractor.candidates()` scans an exact persisted source span with conservative rule patterns. Supported explicit constructions include:

- named supplier, customer, foundry, manufacturer, distributor, partner, or competitor statements;
- reliance or dependency statements naming a supplier or manufacturer;
- named or unnamed customer concentration as a percentage of revenue;
- named or unnamed supplier concentration as a percentage of purchases or supply.

`RelationshipService.extract_span()` validates company ownership, creates schema-validated candidates, resolves only unambiguous companies, persists the observation, and links the exact evidence span. It never executes generated code or invents a counterparty from graph proximity.

## Point-In-Time Reads

`RelationshipRepository.list_current()` selects the latest observation known by the requested `as_of`, then applies validity dates. `RelationshipService.network()` removes records without inspectable evidence and reports incomplete or truncated coverage. Historical observations remain available through `RelationshipService.history()`.

Absence of an edge is never interpreted as absence of the economic relationship. Public companies often disclose only material or concentrated relationships.

## API And UI

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v3/companies/{ticker}/relationships` | Return source-backed current edges with direction, type, confidence, `as_of`, and optional filters. |
| `GET /api/v3/companies/{ticker}/relationships/{relationship_id}` | Return append-only observation history and evidence by observation. |
| `POST /api/v3/companies/{ticker}/relationships/{relationship_id}/overrides` | Persist an evidence-backed human correction. This is an advanced local API, not an ordinary graph action. |

The React view provides direction/type/confidence filters, a one-hop graph, resolved-company navigation, dashed unresolved nodes, edge history, exact source dialogs, and a complete keyboard-accessible table. The visual graph is capped at 16 filtered edges to avoid an unreadable hairball; the table retains every returned edge. On narrow screens the graph scrolls horizontally rather than shrinking labels into illegibility.

## Limitations

- The extractor recognizes explicit language, not every possible legal or financial phrasing.
- Resolved identity does not prove contract scope, exclusivity, or current economic materiality.
- Exposure units retain issuer wording and must not be combined unless they are compatible.
- The graph must not be used to manufacture unsupported peers, network scores, or automated trades.
