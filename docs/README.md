# GBB Terminal Documentation

GBB Terminal is a local-first US equity research and option lifecycle application. Domain code lives under the `gbb_terminal` Python namespace; `app/` contains only the browser interface.

## Module map

| Area | Business definition | Documentation |
| --- | --- | --- |
| Architecture | Boundaries, data flow, path resolution, and deployment seams | [Architecture](architecture.md) |
| Configuration | Local YAML preferences, environment overrides, and provider keys | [`conf/README.md`](../conf/README.md) |
| API | Legacy-compatible and V2 HTTP contracts | [API](api.md) |
| Strategy Model V2 | Templates, instances, parameters, rule graphs, and research runs | [Strategy Model V2](strategy-model-v2.md) |
| Strategy engine | Safe declarative rule evaluation and semantic identity | [Strategy engine](strategy-engine.md) |
| Backtesting | Execution assumptions, metrics, benchmarks, search, and portfolios | [Backtesting](backtesting.md) |
| Indicators | Approved price, trend, volatility, volume, breakout, and relative functions | [Indicators](indicators.md) |
| Option Lab | Position construction, American pricing, scenarios, and lifecycle accounting | [Option Lab](option-lab.md) |
| Public providers | Yahoo, SEC, FINRA, FRED, OCC, timestamps, and fallback rules | [Providers](providers.md) |
| Storage | DuckDB tables, migrations, caches, and ledgers | [Storage](storage.md) |
| LLM translator | Natural language to validated strategy data | [LLM translator](llm-translator.md) |
| Observability | Structured events and rotating local logs | [Logging](logging.md) |
| Browser | Vanilla JavaScript workflow and chart interactions | [Frontend](frontend.md) |
| Release readiness | Completed research gates and deferred launch-stability checks | [Release Checklist](release-checklist.md) |
| Community extensions | Adding indicators and strategy templates safely | [Strategy Plugin Guide](strategy-plugin-guide.md) |

## Safety invariants

1. Generated or imported Python is never evaluated.
2. Research keeps losing results and passive comparisons visible.
3. External observations carry publication-aware timing where available.
4. Option outputs are labelled theoretical unless contract marks were actually captured.
5. Local runtime data and secrets are never tracked by Git.
