from __future__ import annotations

import pandas as pd

from ..strategy.models import ExecutionAssumptions


def apply_execution(
    frame: pd.DataFrame,
    assumptions: ExecutionAssumptions,
) -> pd.DataFrame:
    executed = frame.copy()
    executed["signal_position"] = executed["position"].astype(float)
    executed["position"] = executed["signal_position"].shift(1).fillna(0)
    executed["daily_return"] = executed["close"].pct_change().fillna(0)
    executed["turnover"] = executed["position"].diff().abs().fillna(executed["position"].abs())
    executed["cost"] = executed["turnover"] * assumptions.one_way_cost_rate
    cash_daily_rate = (1 + assumptions.annual_cash_rate) ** (1 / 252) - 1
    executed["strategy_return"] = (
        executed["position"] * executed["daily_return"]
        + (1 - executed["position"].abs()).clip(lower=0) * cash_daily_rate
        - executed["cost"]
    )
    executed["equity"] = (1 + executed["strategy_return"]).cumprod()
    executed["benchmark_equity"] = (1 + executed["daily_return"]).cumprod()
    return executed

