# Strategy Plugin Guide

GBB Terminal “plugins” are declarative templates and registered calculation functions. They are not downloaded Python scripts.

## Add an indicator

1. Add metadata to `IndicatorRegistry.DEFINITIONS`.
2. Implement deterministic `IndicatorRegistry.calculate()` behavior using only current and earlier observations.
3. Validate every parameter and bound computational cost.
4. Add a no-future-data unit test comparing a full series with a historical prefix.
5. Document source fields, units, warm-up length, and known limitations.

## Add a strategy family

1. Add a versioned `StrategyTemplate` to `strategy/catalogue.py`.
2. Declare every `ParameterSpec` and required dataset.
3. Compile its rule graph in `_configuration()` or route portfolio logic to a dedicated engine.
4. Keep entry and exit rules deterministic and explainable.
5. Add serialization, duplicate-key, and signal-equivalence tests.

Manual chart annotations may be exploratory features but must not enter historical testing. For example, Fibonacci backtests use deterministic rolling swing anchors; hindsight-selected manual anchors are prohibited.

