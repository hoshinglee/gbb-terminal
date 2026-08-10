# GBB Terminal Documentation

GBB Terminal is a local-first US equity research and option lifecycle application. Domain code lives under the `gbb_terminal` Python namespace; `app/` contains only the browser interface.

## Module map

| Area | Business definition | Documentation |
| --- | --- | --- |
| Architecture | Boundaries, data flow, path resolution, and deployment seams | [Architecture](architecture.md) |
| System diagrams | Runtime, frontend state, research sequence, DuckDB model, and build fallback | [System Diagrams](system-diagrams.md) |
| Configuration | Local YAML preferences, environment overrides, and provider keys | [`conf/README.md`](../conf/README.md) |
| API | Legacy-compatible V2 research contracts and strict V3 Company Intelligence contracts | [API](api.md) |
| Company Intelligence | Canonical company identity, security history, resolution, and SEC directory sync | [Company Intelligence](company-intelligence.md) |
| Financial metrics | Versioned SEC concept mappings, units, annual/quarterly/TTM views, derivations, warnings, and lineage | [Financial Metrics](financial-metrics.md) |
| Strategy Model V2 | Templates, instances, parameters, rule graphs, and research runs | [Strategy Model V2](strategy-model-v2.md) |
| Strategy engine | Safe declarative rule evaluation and semantic identity | [Strategy engine](strategy-engine.md) |
| Backtesting | Execution assumptions, metrics, benchmarks, search, and portfolios | [Backtesting](backtesting.md) |
| Indicators | Approved price, trend, volatility, volume, breakout, and relative functions | [Indicators](indicators.md) |
| Option Lab | Position construction, American pricing, scenarios, and lifecycle accounting | [Option Lab](option-lab.md) |
| Public providers | Yahoo, SEC, FINRA, FRED, OCC, timestamps, and fallback rules | [Providers](providers.md) |
| Storage | DuckDB tables, migrations, caches, and ledgers | [Storage](storage.md) |
| LLM translator | Natural language to validated strategy data | [LLM translator](llm-translator.md) |
| Observability | Structured events and rotating local logs | [Logging](logging.md) |
| Browser | Four React research canvases, shadcn/ui interactions, financial charts, direct ticker navigation, and vanilla migration fallback | [Frontend](frontend.md) |
| Market replay | Candles, interval aggregation, overlays, volume, RSI, and MACD | [Market Replay](market-replay.md) |
| Strategy Lab UX | Implemented research-canvas interaction model and remaining panel migration | [Strategy Lab UX](strategy-lab-ux.md) |
| Release readiness | Completed research gates and deferred launch-stability checks | [Release Checklist](release-checklist.md) |
| Product backlog | Completed laboratory foundations and the 0.7–0.9 Company Intelligence direction | [Product Backlog](product-backlog.md) |
| Community extensions | Adding indicators and strategy templates safely | [Strategy Plugin Guide](strategy-plugin-guide.md) |

## Safety invariants

1. Generated or imported Python is never evaluated.
2. Research keeps losing results and passive comparisons visible.
3. External observations carry publication-aware timing where available.
4. Option outputs are labelled theoretical unless contract marks were actually captured.
5. Local runtime data and secrets are never tracked by Git.
