from __future__ import annotations

import numpy as np
import pandas as pd

from ..strategy.models import ExecutionAssumptions


def apply_execution(frame: pd.DataFrame, assumptions: ExecutionAssumptions) -> pd.DataFrame:
    """Execute close-derived target positions at the following session's open."""
    required = {"open", "close", "position"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Execution frame is missing: {', '.join(sorted(missing))}.")
    executed = frame.copy()
    executed["signal_position"] = executed["position"].astype(float)
    executed["position"] = executed["signal_position"].shift(assumptions.signal_lag_sessions).fillna(0.0)
    previous_position = executed["position"].shift(1).fillna(0.0)

    previous_close = executed["close"].shift(1)
    executed["overnight_return"] = (executed["open"] / previous_close - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    executed["intraday_return"] = (executed["close"] / executed["open"] - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    executed["daily_return"] = executed["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    overnight_factor = 1 + previous_position * executed["overnight_return"]
    intraday_factor = 1 + executed["position"] * executed["intraday_return"]
    executed["gross_strategy_return"] = overnight_factor * intraday_factor - 1

    executed["turnover"] = (executed["position"] - previous_position).abs()
    executed["cost"] = executed["turnover"] * assumptions.one_way_cost_rate
    cash_daily_rate = (1 + assumptions.annual_cash_rate) ** (1 / 252) - 1
    executed["cash_return"] = ((previous_position == 0) & (executed["position"] == 0)).astype(float) * cash_daily_rate
    net_factor = 1 + executed["gross_strategy_return"] + executed["cash_return"] - executed["cost"]
    executed["insolvent"] = net_factor <= 0
    executed["strategy_return"] = net_factor.clip(lower=1e-9) - 1
    executed["equity"] = (1 + executed["strategy_return"]).cumprod()
    executed["equity_before"] = executed["equity"].shift(1).fillna(1.0)
    executed["benchmark_equity"] = (1 + executed["daily_return"]).cumprod()
    executed["fill_price"] = executed["open"].where(executed["turnover"] > 0)
    return executed
