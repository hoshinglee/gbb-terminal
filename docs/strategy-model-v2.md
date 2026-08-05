# Strategy Model V2

## Business definition

A strategy is a reproducible research hypothesis. Its identity includes rules, parameters, instrument scope, benchmark, timeframe, risk, and execution assumptions. Internal semantic hashes prevent duplicates but are hidden from ordinary users.

## Models

- `ParameterSpec`: label, type, unit, default, bounds, step, adaptive modes, and search eligibility.
- `StrategyTemplate`: versioned strategy family, required datasets, parameter schema, and rule graph.
- `StrategyInstance`: selected values and modes plus ticker/universe, benchmark, timeframe, risk, and execution assumptions.
- `ResearchRun`: immutable strategy instance, data snapshot dates, engine version, validation design, tested settings, and results.

Canonical JSON is the system format. YAML v1 remains available only for advanced import/export and legacy natural-language proposals.

## Functions

- `StrategyCatalogue.list_templates()` returns all built-in templates.
- `StrategyCatalogue.create_instance(template_id, values, **scope)` validates selected values.
- `StrategyCatalogue.build(instance)` compiles a single-instrument template into a `DeclarativeStrategy`.
- `StrategyInstance.semantic_key()` creates the internal duplicate-prevention identity.

Built-in families cover SMA, EMA, MACD, RSI, Bollinger Bands, Donchian channels, confirmed Darvas boxes, deterministic Fibonacci rolling swings, benchmark-relative strength, volume filters, and ranked peer portfolios.

