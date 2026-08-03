# Indicator Registry

Source: `app/indicators.py`

## Business definition

The indicator registry is the approved vocabulary available to strategies. It lets product users compose rules without adding Python for every combination while keeping calculations deterministic.

## Available indicators

| Type | Inputs | Business meaning |
| --- | --- | --- |
| `price` | `source` | Direct OHLCV field used in threshold comparisons. |
| `sma` | `source`, `window` | Average value over a fixed number of sessions. |
| `ema` | `source`, `window` | Moving average that reacts faster to recent observations. |
| `rsi` | `source`, `window` | Momentum oscillator used for overbought/oversold rules. |
| `volume_sma` | `window` | Baseline trading activity for volume confirmation. |

## Functions

- `IndicatorRegistry.calculate(history, specification)` validates and calculates one indicator.
- `IndicatorRegistry.catalogue()` returns API-readable indicator metadata.
- `technical_indicator_snapshot(history, requests)` calculates named requests such as `sma_20`, `rsi_14`, or `volume_sma_20`.

Add future indicators to the registry and document their required parameters. Do not allow arbitrary function names from YAML.
