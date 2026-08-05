# Strategy Engine

Sources: `src/gbb_terminal/strategy/factory.py` and `src/gbb_terminal/strategy/catalogue.py`

## Business definition

The strategy engine converts a validated trading definition into positions, trades, returns, and benchmark comparisons. A strategy is data plus approved behavior—not generated Python code.

## Core objects and functions

| Name | Definition |
| --- | --- |
| `Strategy` | Abstract contract requiring entry/exit criteria, position generation, metadata, and YAML serialization. |
| `DeclarativeStrategy` | Concrete subclass that interprets approved YAML indicators and criteria. |
| `StrategyFactory.from_yaml` | Safely parses YAML and creates a validated strategy. |
| `StrategyFactory.validate` | Rejects unsupported indicators, invalid aliases, directions, criteria, risk settings, and operators. |
| `StrategyFactory.strategy_key` | Produces a stable semantic identity independent of names, wording, YAML formatting, and indicator aliases. |
| `moving_average_configuration` | Creates the built-in MA crossover YAML structure. |
| `parse_strategy` | Deterministic MA parser used when no LLM key is configured. |
| `run_research_backtest` | Cost-aware evidence engine in `backtesting/engine.py`. |
| `run_parameter_search` | Guarded walk-forward parameter evaluation in `backtesting/parameter_search.py`. |

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
risk:
  stop_loss_percent: 8
```

Each comparison may include `right_multiplier`. For example, `{left: daily_volume, operator: greater_or_equal, right: average_volume, right_multiplier: 1.5}` means current volume must be at least 150% of its configured average.

`risk` supports fixed stop/profit percentages, trailing stops, ATR-multiple stops, and maximum holding sessions. Strategy names use title format while preserving trading acronyms such as MA, SMA, EMA, MACD, RSI, ATR, OBV, and SPY.

## Trade ledger semantics

A closed trade contains entry and exit dates/prices plus realized P&L. If a position remains active at the final observation, the result contains an `Open` row with `asOfDate`, current price, and unrealized P&L. Run metrics count closed and open trades separately.

## Why not `eval`

`eval` would allow external text to execute arbitrary Python and access local data. The declarative interpreter exposes only explicitly registered indicators and comparison operators, making saved configurations inspectable and portable.
