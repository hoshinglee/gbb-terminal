# Indicator Registry

Source: `src/gbb_terminal/strategy/indicators/registry.py`

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
| `macd`, `macd_signal` | fast, slow, signal windows | Trend momentum and confirmation. |
| `bollinger_upper`, `bollinger_lower`, `zscore` | source, window, deviations | Mean-reversion boundaries. |
| `atr`, `volatility`, `gap` | window where applicable | Price risk, dispersion, and overnight movement. |
| `donchian_high`, `donchian_low` | window | Prior channel levels without future observations. |
| `darvas_high`, `darvas_low` | window, confirmation bars | Confirmed deterministic box boundaries. |
| `fibonacci_level` | window, ratio | Rolling-swing level without manual hindsight anchors. |
| `obv` | none | Directional cumulative volume. |
| `relative_strength` | window, aligned benchmark | Excess rolling return over the selected benchmark. |

## Functions

- `IndicatorRegistry.calculate(history, specification)` validates and calculates one indicator.
- `IndicatorRegistry.catalogue()` returns API-readable indicator metadata.
- `technical_indicator_snapshot(history, requests)` calculates named requests such as `sma_20`, `rsi_14`, or `volume_sma_20`.

Add future indicators to the registry and document their required parameters. Do not allow arbitrary function names from YAML.
