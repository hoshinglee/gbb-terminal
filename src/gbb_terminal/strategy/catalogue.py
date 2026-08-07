from __future__ import annotations

from copy import deepcopy
from typing import Any

from .factory import DeclarativeStrategy, StrategyFactory, sentence_case, title_case
from .models import DataRequirement, ParameterSpec, ParameterType, StrategyInstance, StrategyTemplate


PRICE_DATA = [DataRequirement(dataset="daily_prices", fields=["open", "high", "low", "close", "volume"])]


def _integer(key: str, label: str, default: int, minimum: int, maximum: int, step: int = 1) -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        parameter_type=ParameterType.INTEGER,
        unit="Sessions",
        default=default,
        minimum=minimum,
        maximum=maximum,
        step=step,
    )


def _number(key: str, label: str, default: float, minimum: float, maximum: float, step: float, unit: str = "") -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        parameter_type=ParameterType.NUMBER,
        unit=unit,
        default=default,
        minimum=minimum,
        maximum=maximum,
        step=step,
    )


BUILT_IN_TEMPLATES = [
    StrategyTemplate(
        template_id="sma-crossover",
        family="Trend",
        name="SMA Crossover",
        description="Enter when a fast simple moving average crosses above a slow moving average.",
        parameters=[_integer("fast_window", "Fast SMA", 10, 2, 50), _integer("slow_window", "Slow SMA", 50, 10, 250, 5)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "crossover", "average": "sma"},
    ),
    StrategyTemplate(
        template_id="ema-crossover",
        family="Trend",
        name="EMA Crossover",
        description="Enter when a fast exponential moving average crosses above a slow exponential moving average.",
        parameters=[_integer("fast_window", "Fast EMA", 12, 2, 50), _integer("slow_window", "Slow EMA", 26, 10, 250, 5)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "crossover", "average": "ema"},
    ),
    StrategyTemplate(
        template_id="macd-trend",
        family="Trend",
        name="MACD Trend",
        description="Enter when MACD crosses above its signal line and exit on the reverse crossover.",
        parameters=[_integer("fast_window", "Fast EMA", 12, 2, 50), _integer("slow_window", "Slow EMA", 26, 10, 250), _integer("signal_window", "Signal EMA", 9, 2, 50)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "macd"},
    ),
    StrategyTemplate(
        template_id="rsi-mean-reversion",
        family="Mean Reversion",
        name="RSI Mean Reversion",
        description="Enter after an oversold RSI reading and exit when RSI returns to its recovery threshold.",
        parameters=[_integer("window", "RSI Window", 14, 2, 100), _number("entry_level", "Oversold Entry", 30, 5, 45, 1), _number("exit_level", "Recovery Exit", 55, 45, 90, 1)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "threshold", "indicator": "rsi"},
    ),
    StrategyTemplate(
        template_id="bollinger-mean-reversion",
        family="Mean Reversion",
        name="Bollinger Mean Reversion",
        description="Enter below the lower Bollinger Band and exit after price recovers through the middle band.",
        parameters=[_integer("window", "Band Window", 20, 5, 100), _number("deviations", "Standard Deviations", 2.0, 0.5, 4.0, 0.1)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "bollinger"},
    ),
    StrategyTemplate(
        template_id="donchian-breakout",
        family="Breakout",
        name="Donchian Breakout",
        description="Enter on a confirmed channel-high breakout and exit below the channel low.",
        parameters=[_integer("entry_window", "Entry Channel", 55, 5, 250), _integer("exit_window", "Exit Channel", 20, 2, 100)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "donchian"},
    ),
    StrategyTemplate(
        template_id="darvas-volume-breakout",
        family="Breakout",
        name="Darvas Volume Breakout",
        description="Enter above a confirmed Darvas box with elevated volume and exit below the box floor.",
        parameters=[_integer("box_window", "Box Window", 20, 5, 100), _integer("confirmation_bars", "Confirmation Bars", 3, 1, 10), _integer("volume_window", "Volume Average", 20, 5, 100), _number("volume_multiplier", "Volume Multiplier", 1.5, 1.0, 5.0, 0.1, "×")],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "darvas_volume"},
    ),
    StrategyTemplate(
        template_id="fibonacci-resistance-breakout",
        family="Breakout",
        name="Fibonacci Resistance Breakout",
        description="Enter when price crosses a deterministic rolling-swing Fibonacci resistance level.",
        parameters=[_integer("window", "Swing Window", 55, 10, 250), _number("ratio", "Retracement Ratio", 0.618, 0.1, 0.9, 0.001)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "fibonacci"},
    ),
    StrategyTemplate(
        template_id="benchmark-relative-strength",
        family="Relative Strength",
        name="Benchmark Relative Strength",
        description="Enter when rolling performance exceeds the selected benchmark and exit after relative strength turns negative.",
        parameters=[_integer("window", "Relative Strength Window", 63, 10, 252), _number("entry_threshold", "Entry Threshold", 2.0, 0.0, 30.0, 0.5, "%")],
        required_datasets=[*PRICE_DATA, DataRequirement(dataset="benchmark_prices", fields=["close"])],
        rule_graph={"kind": "relative_strength"},
    ),
    StrategyTemplate(
        template_id="relative-strength-rotation",
        family="Portfolio",
        name="Relative Strength Rotation",
        description="Rank a user-defined stock universe by trailing return and hold the strongest equal-weight names.",
        parameters=[_integer("lookback_window", "Ranking Lookback", 63, 10, 252), _integer("top_n", "Number Of Holdings", 3, 1, 20), _integer("rebalance_sessions", "Rebalance Frequency", 21, 5, 126)],
        required_datasets=PRICE_DATA,
        rule_graph={"kind": "ranked_portfolio"},
    ),
]


class StrategyCatalogue:
    def __init__(self) -> None:
        self._templates = {template.template_id: template for template in BUILT_IN_TEMPLATES}

    def list_templates(self) -> list[StrategyTemplate]:
        return list(self._templates.values())

    def get(self, template_id: str) -> StrategyTemplate:
        try:
            return self._templates[template_id]
        except KeyError as error:
            raise ValueError(f"Unknown strategy template '{template_id}'.") from error

    def create_instance(
        self,
        template_id: str,
        values: dict[str, int | float | bool | str] | None = None,
        **overrides: Any,
    ) -> StrategyInstance:
        template = self.get(template_id)
        for legacy_scope in ("ticker", "universe", "benchmark", "sector_benchmark", "timeframe", "execution"):
            overrides.pop(legacy_scope, None)
        selected = {parameter.key: parameter.default for parameter in template.parameters}
        selected.update(values or {})
        self._validate_values(template, selected)
        return StrategyInstance(
            template_id=template.template_id,
            template_version=template.version,
            name=title_case(str(overrides.pop("name", template.name))),
            description=sentence_case(str(overrides.pop("description", template.description))),
            parameter_values=selected,
            **overrides,
        )

    def build(self, instance: StrategyInstance) -> DeclarativeStrategy:
        template = self.get(instance.template_id)
        if instance.template_version != template.version:
            raise ValueError(
                f"Strategy template version {instance.template_version} is unavailable; "
                f"'{template.template_id}' currently requires version {template.version}."
            )
        if template.rule_graph.get("kind") == "ranked_portfolio":
            raise ValueError("Ranked portfolio templates must run through the portfolio engine.")
        values = deepcopy(instance.parameter_values)
        self._validate_values(template, values)
        configuration = _configuration(template, values)
        configuration["name"] = instance.name
        configuration["description"] = instance.description
        configuration["risk"] = instance.risk
        return StrategyFactory.create(configuration)  # type: ignore[return-value]

    @staticmethod
    def _validate_values(template: StrategyTemplate, values: dict[str, Any]) -> None:
        expected = {parameter.key: parameter for parameter in template.parameters}
        unknown = set(values) - set(expected)
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}.")
        for key, parameter in expected.items():
            if key not in values:
                raise ValueError(f"Missing parameter '{key}'.")
            value = values[key]
            if parameter.parameter_type == ParameterType.INTEGER and (isinstance(value, bool) or int(value) != value):
                raise ValueError(f"{parameter.label} must be an integer.")
            if isinstance(value, (int, float)):
                if parameter.minimum is not None and value < parameter.minimum:
                    raise ValueError(f"{parameter.label} must be at least {parameter.minimum:g}.")
                if parameter.maximum is not None and value > parameter.maximum:
                    raise ValueError(f"{parameter.label} must be at most {parameter.maximum:g}.")
        if "fast_window" in values and "slow_window" in values and int(values["fast_window"]) >= int(values["slow_window"]):
            raise ValueError("The fast window must be shorter than the slow window.")
        if template.rule_graph.get("kind") == "ranked_portfolio" and int(values["top_n"]) < 1:
            raise ValueError("A ranked portfolio must hold at least one symbol.")

    def is_portfolio(self, template_id: str) -> bool:
        return self.get(template_id).rule_graph.get("kind") == "ranked_portfolio"


def _configuration(template: StrategyTemplate, values: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version": 1,
        "name": template.name,
        "description": template.description,
        "direction": template.direction,
        "risk": {},
    }
    kind = template.rule_graph["kind"]
    if kind == "crossover":
        average = template.rule_graph["average"]
        base.update(
            indicators={
                "fast_average": {"type": average, "source": "close", "window": int(values["fast_window"])},
                "slow_average": {"type": average, "source": "close", "window": int(values["slow_window"])},
            },
            entry={"all": [{"left": "fast_average", "operator": "crosses_above", "right": "slow_average"}]},
            exit={"any": [{"left": "fast_average", "operator": "crosses_below", "right": "slow_average"}]},
        )
    elif kind == "macd":
        parameters = {key: int(values[key]) for key in ("fast_window", "slow_window", "signal_window")}
        base.update(
            indicators={"macd": {"type": "macd", **parameters}, "signal": {"type": "macd_signal", **parameters}},
            entry={"all": [{"left": "macd", "operator": "crosses_above", "right": "signal"}]},
            exit={"any": [{"left": "macd", "operator": "crosses_below", "right": "signal"}]},
        )
    elif kind == "threshold":
        base.update(
            indicators={"rsi": {"type": "rsi", "source": "close", "window": int(values["window"])}},
            entry={"all": [{"left": "rsi", "operator": "less_than", "right": float(values["entry_level"])}]},
            exit={"any": [{"left": "rsi", "operator": "greater_than", "right": float(values["exit_level"])}]},
        )
    elif kind == "bollinger":
        specification = {"source": "close", "window": int(values["window"]), "deviations": float(values["deviations"])}
        base.update(
            indicators={"price": {"type": "price", "source": "close"}, "lower_band": {"type": "bollinger_lower", **specification}, "middle_band": {"type": "sma", "source": "close", "window": int(values["window"])}},
            entry={"all": [{"left": "price", "operator": "crosses_below", "right": "lower_band"}]},
            exit={"any": [{"left": "price", "operator": "crosses_above", "right": "middle_band"}]},
        )
    elif kind == "donchian":
        base.update(
            indicators={"price": {"type": "price", "source": "close"}, "channel_high": {"type": "donchian_high", "window": int(values["entry_window"])}, "channel_low": {"type": "donchian_low", "window": int(values["exit_window"])}},
            entry={"all": [{"left": "price", "operator": "crosses_above", "right": "channel_high"}]},
            exit={"any": [{"left": "price", "operator": "crosses_below", "right": "channel_low"}]},
        )
    elif kind == "darvas_volume":
        box = {"window": int(values["box_window"]), "confirmation_bars": int(values["confirmation_bars"])}
        base.update(
            indicators={
                "price": {"type": "price", "source": "close"},
                "volume": {"type": "price", "source": "volume"},
                "box_high": {"type": "darvas_high", **box},
                "box_low": {"type": "darvas_low", **box},
                "average_volume": {"type": "volume_sma", "window": int(values["volume_window"])},
            },
            entry={"all": [
                {"left": "price", "operator": "crosses_above", "right": "box_high"},
                {"left": "volume", "operator": "greater_than", "right": "average_volume", "right_multiplier": float(values["volume_multiplier"])},
            ]},
            exit={"any": [{"left": "price", "operator": "crosses_below", "right": "box_low"}]},
        )
    elif kind == "fibonacci":
        base.update(
            indicators={"price": {"type": "price", "source": "close"}, "resistance": {"type": "fibonacci_level", "window": int(values["window"]), "ratio": float(values["ratio"])}},
            entry={"all": [{"left": "price", "operator": "crosses_above", "right": "resistance"}]},
            exit={"any": [{"left": "price", "operator": "crosses_below", "right": "resistance"}]},
        )
    elif kind == "relative_strength":
        base.update(
            indicators={"relative_strength": {"type": "relative_strength", "window": int(values["window"])}},
            entry={"all": [{"left": "relative_strength", "operator": "greater_than", "right": float(values["entry_threshold"])}]},
            exit={"any": [{"left": "relative_strength", "operator": "less_than", "right": 0.0}]},
        )
    else:
        raise ValueError(f"Unsupported template rule graph '{kind}'.")
    return base


catalogue = StrategyCatalogue()
