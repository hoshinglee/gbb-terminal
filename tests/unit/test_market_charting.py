from __future__ import annotations

from gbb_terminal.market_data.charting import build_market_chart


def test_market_chart_aggregates_ohlcv_and_calculates_standard_indicators(price_history):
    chart = build_market_chart(price_history)

    assert chart["defaultInterval"] == "day"
    assert set(chart["intervals"]) == {"day", "week", "month", "year"}
    assert len(chart["intervals"]["day"]) == len(price_history)
    assert len(chart["intervals"]["week"]) < len(chart["intervals"]["day"])
    assert len(chart["intervals"]["month"]) < len(chart["intervals"]["week"])

    first_week = chart["intervals"]["week"][0]
    source_week = price_history.loc[first_week["periodStart"] : first_week["periodEnd"]]
    assert first_week["open"] == round(float(source_week["Open"].iloc[0]), 4)
    assert first_week["high"] == round(float(source_week["High"].max()), 4)
    assert first_week["low"] == round(float(source_week["Low"].min()), 4)
    assert first_week["close"] == round(float(source_week["Close"].iloc[-1]), 4)
    assert first_week["volume"] == round(float(source_week["Volume"].sum()))

    mature_day = chart["intervals"]["day"][40]
    assert set(mature_day["indicators"]) == {
        "sma20",
        "ema20",
        "bollingerMiddle20",
        "bollingerUpper20",
        "bollingerLower20",
        "volumeSma20",
        "rsi14",
        "macd",
        "macdSignal",
        "macdHistogram",
    }
    assert all(value is not None for value in mature_day["indicators"].values())


def test_market_chart_indicators_do_not_change_when_future_data_is_appended(price_history):
    earlier = build_market_chart(price_history.iloc[:300])["intervals"]["day"]
    extended = build_market_chart(price_history)["intervals"]["day"][:300]

    assert earlier == extended


def test_market_chart_carries_research_state_to_aggregated_candles(price_history):
    history = price_history.copy()
    history["Position"] = 0
    history.loc[history.index[-10]:, "Position"] = 1
    history["SignalPosition"] = history["Position"]
    history["StrategyEquity"] = 1 + history["Close"].pct_change().fillna(0).cumsum()

    chart = build_market_chart(history)

    assert chart["intervals"]["day"][-1]["position"] == 1
    assert chart["intervals"]["month"][-1]["signalPosition"] == 1
    assert chart["intervals"]["year"][-1]["strategyEquity"] is not None


def test_market_chart_uses_pre_evaluation_history_for_indicator_warmup(price_history):
    visible_start = price_history.index[100]
    visible_end = price_history.index[140]

    chart = build_market_chart(price_history, visible_start=visible_start, visible_end=visible_end)
    first_day = chart["intervals"]["day"][0]

    assert len(chart["intervals"]["day"]) == 41
    assert first_day["periodStart"] == visible_start.strftime("%Y-%m-%d")
    assert first_day["indicators"]["sma20"] is not None
    assert first_day["indicators"]["bollingerUpper20"] is not None
