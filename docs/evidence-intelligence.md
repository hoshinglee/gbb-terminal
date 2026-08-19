# Evidence Intelligence

Sources: `src/gbb_terminal/intelligence/evidence_models.py`, `src/gbb_terminal/intelligence/evidence_repository.py`, and `src/gbb_terminal/intelligence/evidence.py`

Evidence Intelligence is the trust layer for source-derived Company Intelligence. A relationship, guidance statement, segment observation, KPI, or future LLM-assisted extraction can reference the exact public document and text span that supports it. Generated summaries never replace that source context.

## Business Definitions

| Concept | Definition |
| --- | --- |
| Evidence document | A versioned public filing, release, annual report, or permitted investor document associated with a canonical `company_id`. |
| Evidence span | Exact source text plus its section, page, offsets, extraction method, and extraction timestamp when available. |
| Claim link | A typed association between an independently addressable evidence span and a structured domain claim. |
| Evidence role | Whether a linked span supports, contextualizes, or contradicts a claim. |
| `known_at` | The earliest timestamp at which the document may be used by a point-in-time consumer. |

Initial document types are `10-k`, `10-q`, `8-k`, `earnings_release`, `annual_report`, `investor_presentation`, and `other`.

## Domain Functions

| Function | Definition |
| --- | --- |
| `EvidenceRepository.save_document()` | Validates company ownership, deduplicates identical source content, and creates a new linked version when the same source identity changes. |
| `EvidenceRepository.save_span()` | Deduplicates exact source locations, persists source context, and marks a pending document as parsed. |
| `EvidenceRepository.mark_parse_failed()` | Records a bounded parser error and prevents unsupported spans from being added. |
| `EvidenceRepository.link_claim()` | Attaches one span to one structured claim with a support, context, or contradiction role. |
| `EvidenceService.documents()` | Resolves a ticker to `company_id`, applies type and `as_of` filters, and reports incomplete or truncated coverage. |
| `EvidenceService.document()` | Returns one document and every persisted span visible at the requested boundary. |
| `EvidenceService.span()` | Returns a span independently from the claim that originally referenced it, together with its source document. |
| `EvidenceService.claim()` | Returns every visible evidence span and support/context/contradiction role linked to a typed claim. |

## Identity And Versioning

- A document source identity is `(company_id, source, external_id)`.
- Exact duplicate content is detected by the source identity plus the SHA-256 content fingerprint and returns the existing record.
- Changed content under the same source identity creates the next `version` and records `supersedes_document_id`; earlier content is not overwritten.
- A span identity is deterministic from its document and exact text/location fingerprint.
- Claim links are additive. Multiple source spans may support the same claim, and one span may be associated with different typed claims.
- Semantic identifiers remain internal implementation details; APIs expose stable IDs so clients can reopen source evidence.

## Point-In-Time Rules

Document collection and claim retrieval filter by document `known_at`. A historical query cannot inspect a later filing, amendment, release, or presentation. `filed_at` and `published_at` preserve source timing, while `retrieved_at` records when the local application obtained the content.

The evidence layer does not infer that public disclosure is exhaustive. Empty results include an explicit incomplete-coverage warning. Absence of a document, span, or business relationship is not evidence that it does not exist.

## Parsing Safety

- A new document starts with `parse_status=pending`.
- Persisting a validated source span transitions it to `parsed`.
- A failed parser records `parse_status=failed` and a bounded error message.
- Failed documents cannot receive spans, and a document with persisted spans cannot later be marked failed.
- LLMs may later propose schema-bound claims and span references, but deterministic validation decides what is persisted. User- or model-generated code is never evaluated.

## Read API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v3/companies/{ticker}/evidence/documents` | List source documents with optional comma-separated `types`, timezone-aware `as_of`, and `limit`. |
| `GET /api/v3/companies/{ticker}/evidence/documents/{document_id}` | Inspect document metadata and every extracted span. |
| `GET /api/v3/companies/{ticker}/evidence/spans/{span_id}` | Inspect one exact source span independently. |
| `GET /api/v3/companies/{ticker}/evidence/claims/{claim_type}/{claim_id}` | Inspect all spans attached to one structured claim. |

The evidence inspection endpoints remain read-only. Release 0.10 adds explicit SEC source-refresh and health endpoints plus a local CLI; see [Public Document Collection](public-document-collection.md).

## Storage

DuckDB schema version 10 adds `evidence_documents`, `evidence_spans`, and `evidence_claim_links`. Schema version 14 adds verified raw document content and refresh diagnostics. All source text, metadata, timestamps, parse state, and claim associations persist locally. Downloaded source files and runtime databases remain excluded from Git.

## Current Boundary

INT-09 through INT-13 establish the reusable evidence and structured business domains. INT-18 supplies the SEC-first collection pipeline that populates those domains while preserving explicit incomplete, failed, and unsupported states.
