# Strategy Engine

Source: `app/strategy.py`

## Business definition

The strategy engine converts a validated trading definition into positions, trades, returns, and benchmark comparisons. A strategy is data plus approved behavior—not generated Python code.

## Core objects and functions

| Name | Definition |
| --- | --- |
| `Strategy` | Abstract contract requiring entry/exit criteria, position generation, metadata, and YAML serialization. |
| `DeclarativeStrategy` | Concrete subclass that interprets approved YAML indicators and criteria. |
| `StrategyFactory.from_yaml` | Safely parses YAML and creates a validated strategy. |
| `StrategyFactory.validate` | Rejects unknown fields, indicators, aliases, directions, and operators. |
| `moving_average_configuration` | Creates the built-in MA crossover YAML structure. |
| `parse_strategy` | Deterministic MA parser used when no LLM key is configured. |
| `run_backtest` | Produces normalized strategy, buy-and-hold, and SPY equity plus metrics and closed trades. |
| `monte_carlo` | Bootstraps daily returns into percentile paths. |

## YAML schema

```yaml
version: 1
name: Long MA5/MA10 Crossover
description: Enter on the bullish crossover and exit on reversal.
direction: long
indicators:
  fast_ma: {type: sma, source: close, window: 5}
  slow_ma: {type: sma, source: close, window: 10}
entry:
  all:
    - {left: fast_ma, operator: crosses_above, right: slow_ma}
exit:
  any:
    - {left: fast_ma, operator: crosses_below, right: slow_ma}
```

## Why not `eval`

`eval` would allow external text to execute arbitrary Python and access local data. The declarative interpreter exposes only explicitly registered indicators and comparison operators, making saved configurations inspectable and portable.
