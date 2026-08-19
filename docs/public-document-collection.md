# Public Document Collection

Sources: `src/gbb_terminal/intelligence/collectors/`, `src/gbb_terminal/intelligence/document_parser.py`, `src/gbb_terminal/intelligence/document_extraction.py`, and `src/gbb_terminal/intelligence/collection_service.py`

Release 0.10 adds an SEC-first ingestion pipeline that turns permitted public filings into locally inspectable Company Intelligence. The collector does not scrape arbitrary finance sites, and a structured claim is never persisted without a linked `EvidenceSpan`.

## Business Workflow

```text
Company identity
→ SEC submissions and filing indexes
→ missing or explicitly refreshed archive documents
→ versioned raw evidence content
→ deterministic HTML / inline-XBRL parsing
→ exact evidence spans
→ validated relationship, operations, and guidance records
```

Supported filing families are 10-K, 10-Q, 8-K, 6-K, and 20-F, including amendments. Relevant EX-99 exhibits are collected from 8-K and 6-K filing indexes and classified as earnings releases or investor presentations from their public descriptions. PDFs and unknown binary formats are retained as source records but explicitly marked unsupported by the deterministic parser.

## Domain Functions

| Function | Definition |
| --- | --- |
| `SECArchiveCollector.discover()` | Reads current and historical SEC submission metadata, preserves filing acceptance as `known_at`, and discovers filing indexes, primary documents, and relevant exhibits. |
| `SECArchiveCollector.download()` | Downloads only the discovered SEC archive document or returns prefetched filing-index content. |
| `PublicDocumentParser.parse()` | Extracts narrative HTML blocks, inline-XBRL contexts, dimensions, units, standard facts, and custom-taxonomy facts without executing document code. |
| `DocumentExtractionService.extract()` | Persists selected narrative spans first, then runs evidence-bound relationship, operating-metric, and guidance extraction. |
| `IntelligenceRefreshService.refresh()` | Coordinates discovery, idempotent local reuse, versioned content storage, parsing, extraction, progress, cancellation, diagnostics, and final coverage. |
| `IntelligenceRefreshService.health()` | Reports latest refresh diagnostics and current Evidence, Network, Operations, and Guidance coverage. |

Operations extraction recognizes issuer dimensions for reportable segments and exact geographies, plus conservative custom-taxonomy KPIs. Guidance extraction stores explicit numeric points/ranges and clear management commitments; ambiguous narrative remains source evidence rather than being converted into a structured claim. The deterministic relationship extractor recognizes direct relationship grammar plus bounded named lists for disclosed suppliers, foundries, contract manufacturers, distributors, and competitors. Every resulting edge still requires the exact source span; unnamed customers and inferred ecosystem participants are not invented.

The HTML parser reads semantic elements and leaf `div` narrative in one linear pass. This matters for inline-XBRL filings that contain many table rows but place business narrative inside `div` elements. Parser-version changes invalidate the parsed-content cache so an unchanged public filing can be safely reprocessed without changing its source identity.

## Status Semantics

Refresh diagnostics distinguish:

- `no_disclosure`: no supported filing or claim was disclosed in the requested window.
- `provider_failed`: SEC discovery or download failed.
- `unsupported_format`: a source exists but the deterministic parser does not support its format.
- `parse_failed`: downloaded content could not be parsed.
- `extraction_failed`: parsing succeeded, but structured extraction failed.
- `unchanged`: the same parsed SEC archive identity and parser version are already cached.
- `parsed`: parsing and structured extraction completed, including a valid result with zero claims.

Existing populated records remain visible when a later refresh finds no new disclosure. The latest refresh item retains that no-disclosure result so the UI does not imply that prior evidence was deleted.

## Refresh Workflows

The Company Intelligence **Sources** tab exposes source health, module coverage, progress, cancellation, warnings, and **Refresh Intelligence Sources**.

Equivalent local CLI commands are:

```bash
gbb-terminal intelligence refresh NVDA
gbb-terminal intelligence refresh NVDA --max-filings 8 --form 10-K --form 8-K
gbb-terminal intelligence health NVDA
```

The API creates a DuckDB-backed local job:

- `POST /api/v3/companies/{ticker}/sources/refresh`
- `GET /api/v3/intelligence-jobs/{job_id}`
- `POST /api/v3/intelligence-jobs/{job_id}/cancel`
- `GET /api/v3/companies/{ticker}/sources/health`

Cancellation is cooperative between documents. Documents completed before cancellation remain available and the refresh result is recorded as cancelled rather than rolled back.

When a refresh asks only for current-report families with exhibits enabled, SEC discovery prioritizes earnings-relevant 8-K items 2.02, 7.01, and 8.01 before newer unrelated current reports. A 6-K remains eligible because foreign issuers do not use the same item taxonomy. This selection improves earnings-release coverage without presenting every current report as an earnings disclosure.

## Storage And Integrity

Raw bytes are stored in `evidence_document_contents`, keyed by immutable evidence-document version. The SHA-256 content hash is verified before persistence. `intelligence_refresh_runs` stores request, counts, coverage, warnings, and terminal state; `intelligence_refresh_items` stores every source-level outcome. SEC accession, form, public URL, filing/publication time, `known_at`, retrieval time, source metadata, parser version, and supersession links remain inspectable.

Repeated refreshes do not duplicate parsed documents or structured claims. Changed content under the same public source identity creates a new linked evidence-document version. Provider throttling is process-safe per adapter and honors `Retry-After` when supplied.

## Current Limits

- The initial deterministic parser supports HTML, XHTML, XML, inline XBRL, and plain text; PDF extraction is intentionally not inferred.
- Public filing language varies. Zero extracted claims means no supported disclosure was found by the current deterministic rules, not that the business has no such relationship, KPI, or guidance.
- Optional schema-bound LLM candidates remain a future extension. No LLM output bypasses evidence and schema validation.
- SEC source data is delayed public information and can be amended.
