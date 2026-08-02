# GBB Terminal Documentation

GBB Terminal is a local-first US equity research application. Its Strategy Lab turns natural-language trading ideas into a constrained YAML definition, validates that definition, builds a `Strategy` object, runs a backtest, and stores the definition and results in DuckDB.

## Module map

| Module | Business purpose | Documentation |
| --- | --- | --- |
| API application | Connect the browser, market data, strategies, and persistence | [API](api.md) |
| Strategy engine | Interpret safe strategy definitions and calculate trades | [Strategy engine](strategy-engine.md) |
| Indicator registry | Provide approved technical indicators to strategies and API clients | [Indicators](indicators.md) |
| LLM translator | Translate natural language into strategy YAML | [LLM translator](llm-translator.md) |
| Market data | Retrieve and normalize Yahoo Finance data | [Market data](market-data.md) |
| Storage | Cache market data and persist catalogue/backtest records | [Storage](storage.md) |
| Logging | Record application, request, strategy, and backtest events | [Logging](logging.md) |
| Browser interface | Present Strategy Lab, stocks/options, and market pulse | [Frontend](frontend.md) |

## Strategy flow

1. A user writes a trading rule or loads a saved strategy.
2. Google AI Studio converts a new instruction into GBB Strategy YAML v1.
3. The browser shows the normalized description, assumptions, semantic key, and YAML for confirmation.
4. `StrategyFactory` parses YAML with `yaml.safe_load` and validates supported fields.
5. `DeclarativeStrategy` calculates only registered indicators and operators.
6. The backtest compares strategy equity with the stock and SPY and returns closed and open trades.
7. DuckDB reuses an existing semantic key or stores one new catalogue definition, then persists the run and closed trades.

No strategy input is passed to Python `eval` or `exec`.
