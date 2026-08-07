# Strategy Model V2

## Business definition

A strategy is a reusable, reproducible research hypothesis. Its identity includes template version, declarative rules, selected parameter values, and risk rules. Ticker, portfolio universe, benchmark, timeframe, and execution costs describe a particular experiment rather than the strategy itself. Cosmetic names, descriptions, and an explicitly selected `fixed` mode do not create a different strategy.

## Models

- `ParameterSpec`: label, type, unit, default, bounds, step, adaptive modes, and search eligibility. Defaults and bounds are validated when templates load.
- `StrategyTemplate`: versioned strategy family, required datasets, parameter schema, and rule graph.
- `StrategyInstance`: selected rule and risk values plus parameter modes. It is the catalogue configuration and contains no instrument or execution scope.
- `ResearchDesign`: ticker or selection universe, market benchmark, relative-strength reference, timeframe, and next-open execution assumptions.
- `DataSnapshot`: symbol, start/end date, row count, canonical OHLCV columns, and deterministic SHA-256 data fingerprint.
- `ResearchRun`: frozen strategy configuration and research design, canonical strategy key, data snapshots, engine version, validation design, tested settings, results, and self-verifying reproducibility key.

Unknown fields are rejected by V2 models rather than silently ignored. Canonical JSON is the system format. YAML v1 remains available only for advanced import/export and legacy natural-language proposals.

## Reproducibility

`create_data_snapshot()` normalizes ordered OHLCV data before hashing it. A price or volume change alters the fingerprint; copying or serializing the same data does not.

`StrategyInstance.semantic_key()` excludes presentation text and research scope. `ResearchRun` includes both the strategy key and canonical research design in its reproducibility key, preventing mismatched strategy, experiment, or data identities from being persisted.

Every built-in single-stock template is tested to produce identical positions before and after JSON serialization. SMA trend, RSI mean-reversion, and Donchian breakout signals are also tested against future-data mutation.

## Built-in families

Built-in families cover SMA, EMA, MACD, RSI, Bollinger Bands, Donchian channels, confirmed Darvas boxes, deterministic Fibonacci rolling swings, benchmark-relative strength, volume filters, and ranked peer portfolios. `StrategyCatalogue.build()` rejects stale template versions and invalid parameter relationships before a strategy reaches the engine.
