from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd
import yaml

from .indicators.registry import IndicatorRegistry


@dataclass(frozen=True)
class StrategySpec:
    strategy_type: str
    name: str
    description: str
    direction: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Strategy(ABC):
    """Base contract for every strategy accepted by the backtest engine."""

    @property
    @abstractmethod
    def entry_criteria(self) -> str:
        pass

    @property
    @abstractmethod
    def exit_criteria(self) -> str:
        pass

    @abstractmethod
    def positions(self, history: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def spec(self) -> StrategySpec:
        pass

    @abstractmethod
    def to_yaml(self) -> str:
        pass


class DeclarativeStrategy(Strategy):
    """A safe Strategy subclass interpreted from validated declarative data."""

    def __init__(self, configuration: dict[str, Any]) -> None:
        self.configuration = StrategyFactory.validate(deepcopy(configuration))

    @property
    def entry_criteria(self) -> str:
        return _criteria_text(self.configuration["entry"])

    @property
    def exit_criteria(self) -> str:
        return _criteria_text(self.configuration["exit"])

    def positions(self, history: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(index=history.index)
        frame["open"] = history["Open"].astype(float)
        frame["high"] = history["High"].astype(float)
        frame["low"] = history["Low"].astype(float)
        frame["close"] = history["Close"].astype(float)
        frame["volume"] = history["Volume"].fillna(0).astype(float) if "Volume" in history else 0.0
        for name, specification in self.configuration["indicators"].items():
            frame[name] = IndicatorRegistry.calculate(history, specification)
        entry_signal = _evaluate_criteria(self.configuration["entry"], frame)
        exit_signal = _evaluate_criteria(self.configuration["exit"], frame)
        active_value = 1 if self.configuration["direction"] == "long" else -1
        risk = self.configuration.get("risk", {})
        if risk.get("atr_stop_multiple") is not None:
            frame["risk_atr"] = IndicatorRegistry.calculate(history, {"type": "atr", "window": int(risk.get("atr_window", 14))})
        position, current, entry_price = [], 0, None
        favorable_price, entry_atr, pending_entry_atr, holding_days = None, None, None, 0
        pending_entry = False
        for row_number, (open_price, close, enter, exit_trade) in enumerate(
            zip(frame["open"], frame["close"], entry_signal.fillna(False), exit_signal.fillna(False))
        ):
            if current == 0 and bool(enter):
                current, pending_entry = active_value, True
                pending_entry_atr = float(frame["risk_atr"].iloc[row_number]) if "risk_atr" in frame and pd.notna(frame["risk_atr"].iloc[row_number]) else None
            elif current != 0:
                if pending_entry:
                    entry_price = float(open_price)
                    favorable_price = float(open_price)
                    entry_atr, pending_entry_atr = pending_entry_atr, None
                    pending_entry = False
                holding_days += 1
                return_percent = (float(close) / float(entry_price) - 1) * 100 * active_value
                favorable_price = max(float(favorable_price), float(close)) if active_value == 1 else min(float(favorable_price), float(close))
                stop_hit = risk.get("stop_loss_percent") is not None and return_percent <= -float(risk["stop_loss_percent"])
                target_hit = risk.get("take_profit_percent") is not None and return_percent >= float(risk["take_profit_percent"])
                trailing_return = (float(close) / float(favorable_price) - 1) * 100 * active_value
                trailing_hit = risk.get("trailing_stop_percent") is not None and trailing_return <= -float(risk["trailing_stop_percent"])
                atr_hit = entry_atr is not None and risk.get("atr_stop_multiple") is not None and (float(close) - float(entry_price)) * active_value <= -entry_atr * float(risk["atr_stop_multiple"])
                time_hit = risk.get("max_holding_days") is not None and holding_days >= int(risk["max_holding_days"])
                if bool(exit_trade) or stop_hit or target_hit or trailing_hit or atr_hit or time_hit:
                    current, entry_price = 0, None
                    favorable_price, entry_atr, pending_entry_atr, holding_days = None, None, None, 0
                    pending_entry = False
            position.append(current)
        frame["position"] = position
        return frame

    def spec(self) -> StrategySpec:
        return StrategySpec(
            strategy_type="declarative",
            name=self.configuration["name"],
            description=self.configuration["description"],
            direction=self.configuration["direction"],
            parameters={
                "indicators": self.configuration["indicators"],
                "entry": self.configuration["entry"],
                "exit": self.configuration["exit"],
                "risk": self.configuration.get("risk", {}),
            },
        )

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.configuration, sort_keys=False)


class StrategyFactory:
    """Creates Strategy objects from validated definitions without eval."""

    OPERATORS = {"crosses_above", "crosses_below", "greater_than", "less_than", "greater_or_equal", "less_or_equal"}

    @classmethod
    def from_yaml(cls, yaml_text: str) -> Strategy:
        try:
            configuration = yaml.safe_load(yaml_text)
        except yaml.YAMLError as error:
            raise ValueError(f"Strategy YAML is invalid: {error}") from error
        if not isinstance(configuration, dict):
            raise ValueError("Strategy YAML must contain a mapping at its root.")
        return DeclarativeStrategy(configuration)

    @classmethod
    def create(cls, definition: dict[str, Any]) -> Strategy:
        if "indicators" in definition:
            return DeclarativeStrategy(definition)
        parameters = definition.get("parameters", definition)
        fast_window = int(parameters["fast_window"])
        slow_window = int(parameters["slow_window"])
        if fast_window > slow_window:
            fast_window, slow_window = slow_window, fast_window
        return DeclarativeStrategy(moving_average_configuration(fast_window, slow_window, definition.get("direction", "long")))

    @classmethod
    def validate(cls, configuration: dict[str, Any]) -> dict[str, Any]:
        required = {"version", "name", "description", "direction", "indicators", "entry", "exit"}
        missing = required - configuration.keys()
        if missing:
            raise ValueError(f"Strategy definition is missing: {', '.join(sorted(missing))}.")
        if configuration["version"] != 1:
            raise ValueError("Only strategy schema version 1 is supported.")
        if configuration["direction"] not in {"long", "short"}:
            raise ValueError("Strategy direction must be long or short.")
        configuration["name"] = title_case(str(configuration["name"]))
        configuration["description"] = sentence_case(str(configuration["description"]))
        if not isinstance(configuration["indicators"], dict) or not configuration["indicators"]:
            raise ValueError("A strategy must define at least one indicator.")
        for name, indicator in configuration["indicators"].items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError(f"Indicator alias '{name}' is invalid.")
            if not isinstance(indicator, dict) or indicator.get("type") not in IndicatorRegistry.DEFINITIONS:
                raise ValueError(f"Indicator '{name}' uses an unsupported type.")
        for section in ("entry", "exit"):
            _validate_criteria(configuration[section], set(configuration["indicators"]), cls.OPERATORS)
        risk = configuration.get("risk", {})
        if not isinstance(risk, dict):
            raise ValueError("Strategy risk settings must be a mapping.")
        for key in risk:
            if key not in {"stop_loss_percent", "take_profit_percent", "trailing_stop_percent", "atr_stop_multiple", "atr_window", "max_holding_days"}:
                raise ValueError(f"Unsupported risk setting '{key}'.")
            value = float(risk[key])
            upper_bound = 500 if key in {"atr_window", "max_holding_days"} else 100
            if value <= 0 or value > upper_bound:
                raise ValueError("Risk settings must be positive and within their supported bounds.")
            risk[key] = int(value) if key in {"atr_window", "max_holding_days"} else value
        if "atr_window" in risk and "atr_stop_multiple" not in risk:
            raise ValueError("An ATR window requires an ATR stop multiple.")
        configuration["risk"] = risk
        return configuration

    @staticmethod
    def strategy_key(strategy: Strategy) -> str:
        configuration = strategy.configuration if isinstance(strategy, DeclarativeStrategy) else yaml.safe_load(strategy.to_yaml())
        aliases = sorted(configuration["indicators"], key=lambda alias: (json.dumps(configuration["indicators"][alias], sort_keys=True), alias))
        alias_map = {alias: f"indicator_{index + 1}" for index, alias in enumerate(aliases)}

        def canonical_criteria(criteria: dict[str, Any]) -> dict[str, Any]:
            group, rules = next(iter(criteria.items()))
            normalized = [{
                "left": alias_map[rule["left"]],
                "operator": rule["operator"],
                "right": alias_map.get(rule["right"], rule["right"]) if isinstance(rule["right"], str) else rule["right"],
                "right_multiplier": rule.get("right_multiplier", 1.0),
            } for rule in rules]
            return {group: sorted(normalized, key=lambda rule: json.dumps(rule, sort_keys=True))}

        canonical = {
            "version": 1,
            "direction": configuration["direction"],
            "indicators": [configuration["indicators"][alias] for alias in aliases],
            "entry": canonical_criteria(configuration["entry"]),
            "exit": canonical_criteria(configuration["exit"]),
            "risk": configuration.get("risk", {}),
        }
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def moving_average_configuration(fast_window: int, slow_window: int, direction: str = "long") -> dict[str, Any]:
    if fast_window <= 0 or slow_window <= 0 or fast_window == slow_window:
        raise ValueError("Moving-average windows must be different positive numbers.")
    if direction not in {"long", "short"}:
        raise ValueError("Direction must be long or short.")
    entry_operator = "crosses_above" if direction == "long" else "crosses_below"
    exit_operator = "crosses_below" if direction == "long" else "crosses_above"
    return {
        "version": 1,
        "name": f"{direction.title()} MA{fast_window}/MA{slow_window} Crossover",
        "description": f"Enter {direction} when MA{fast_window} crosses its MA{slow_window} confirmation and exit on the reverse crossover.",
        "direction": direction,
        "indicators": {
            "fast_ma": {"type": "sma", "source": "close", "window": fast_window},
            "slow_ma": {"type": "sma", "source": "close", "window": slow_window},
        },
        "entry": {"all": [{"left": "fast_ma", "operator": entry_operator, "right": "slow_ma"}]},
        "exit": {"any": [{"left": "fast_ma", "operator": exit_operator, "right": "slow_ma"}]},
        "risk": {},
    }


def title_case(value: str) -> str:
    formatted = re.sub(r"[_-]+", " ", " ".join(value.strip().split())).title()
    formatted = re.sub(r"\b(Macd|Ma|Sma|Ema|Rsi|Spy|Atr|Obv)(\d*)\b", lambda match: match.group(1).upper() + match.group(2), formatted)
    return re.sub(r"\bP&L\b", "P&L", formatted)


def sentence_case(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return "Strategy description."
    cleaned = cleaned[:1].upper() + cleaned[1:]
    cleaned = re.sub(r"\b(macd|ma|sma|ema|rsi|spy|atr|obv)(\d*)\b", lambda match: match.group(1).upper() + match.group(2), cleaned, flags=re.IGNORECASE)
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def parse_strategy(instruction: str) -> Strategy:
    normalized = " ".join(instruction.lower().replace("moving average", "ma").split())
    risk = _parse_risk_settings(normalized)
    short_requested = bool(re.search(r"\bshort\b", normalized))
    if "darvas" in normalized:
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_darvas_strategy(normalized, risk)
    elif "fibonacci" in normalized or re.search(r"\bfib\b", normalized):
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_fibonacci_strategy(normalized, risk)
    elif "bollinger" in normalized or re.search(r"\bboll\b", normalized):
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_bollinger_strategy(normalized, risk)
    elif "donchian" in normalized:
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_donchian_strategy(normalized, risk)
    elif re.search(r"\brsi\s*\d*\b", normalized):
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_rsi_strategy(normalized, risk)
    elif "macd" in normalized:
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_macd_strategy(normalized, risk)
    elif "relative strength" in normalized:
        if short_requested:
            raise ValueError("Local translation currently supports short direction only for moving-average crossovers.")
        strategy = _parse_relative_strength_strategy(normalized, risk)
    else:
        strategy = _parse_average_strategy(normalized, risk)
    return _with_risk_description(strategy, risk)


def _catalogue_strategy(template_id: str, values: dict[str, int | float], risk: dict[str, float]) -> DeclarativeStrategy:
    from .catalogue import catalogue

    return catalogue.build(catalogue.create_instance(template_id, values, risk=risk))


def _first_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _required_number(text: str, patterns: list[str], message: str) -> float:
    value = _first_number(text, patterns)
    if value is None:
        raise ValueError(message)
    return value


def _parse_risk_settings(normalized: str) -> dict[str, float]:
    risk: dict[str, float] = {}
    trailing_patterns = [
        r"\btrailing\s+stop(?:\s+loss)?(?:\s+of|\s+at)?\s*(\d+(?:\.\d+)?)\s*%",
        r"\btrail(?:ing)?\s+(?:the\s+position\s+)?(?:by\s+)?(\d+(?:\.\d+)?)\s*%",
        r"\b(\d+(?:\.\d+)?)\s*%\s+trailing\s+stop(?:\s+loss)?\b",
    ]
    trailing_matches = [match for pattern in trailing_patterns if (match := re.search(pattern, normalized))]
    if trailing_matches:
        risk["trailing_stop_percent"] = float(trailing_matches[0].group(1))
    risk_text = normalized
    for match in trailing_matches:
        risk_text = f"{risk_text[:match.start()]}{' ' * (match.end() - match.start())}{risk_text[match.end():]}"
    stop_loss = _first_number(
        risk_text,
        [
            r"\bstop(?:\s|-)?loss(?:\s+of|\s+at)?\s*(\d+(?:\.\d+)?)\s*%",
            r"\b(\d+(?:\.\d+)?)\s*%\s+(?:fixed\s+)?stop(?:\s|-)?loss\b",
            r"\b(\d+(?:\.\d+)?)\s*%\s+(?:fixed\s+)?stop\b",
            r"\b(?:maximum|max)\s+loss(?:\s+of|\s+at)?\s*(\d+(?:\.\d+)?)\s*%",
        ],
    )
    if stop_loss is not None:
        risk["stop_loss_percent"] = stop_loss
    take_profit = _first_number(
        normalized,
        [
            r"\btake(?:\s|-)?profit(?:\s+of|\s+at)?\s*(\d+(?:\.\d+)?)\s*%",
            r"\bprofit\s+target(?:\s+of|\s+at)?\s*(\d+(?:\.\d+)?)\s*%",
            r"\b(\d+(?:\.\d+)?)\s*%\s+(?:take(?:\s|-)?profit|profit\s+target)\b",
        ],
    )
    if take_profit is not None:
        risk["take_profit_percent"] = take_profit
    atr_multiple = _first_number(
        normalized,
        [r"\b(\d+(?:\.\d+)?)\s*(?:x|times)\s+(?:the\s+)?atr\b", r"\batr(?:\s+stop)?\s+(\d+(?:\.\d+)?)\s*(?:x|times)\b"],
    )
    if atr_multiple is not None:
        risk["atr_stop_multiple"] = atr_multiple
        atr_window = _first_number(normalized, [r"\batr\s*[- ]?(\d+)\b"])
        if atr_window is not None:
            risk["atr_window"] = atr_window
    max_holding = _first_number(
        normalized,
        [
            r"\b(?:maximum|max)\s+holding(?:\s+period)?(?:\s+of)?\s*(\d+)\s*(?:days?|bars?|sessions?)\b",
            r"\bexit\s+after\s+(\d+)\s*(?:days?|bars?|sessions?)\b",
        ],
    )
    if max_holding is not None:
        risk["max_holding_days"] = max_holding
    return risk


def _volume_parameters(normalized: str) -> tuple[int, float]:
    window = _required_number(
        normalized,
        [
            r"\bvolume[^;]{0,100}?its\s+(\d+)\s*[- ]?(?:day|bar|session)\s+average",
            r"\b(\d+)\s*[- ]?(?:day|bar|session)\s+(?:average\s+)?volume",
            r"\bvolume\s+(?:average|sma)\s*(\d+)\b",
        ],
        "Volume filters need an explicit average window, for example '20-day average volume'.",
    )
    multiplier = _required_number(
        normalized,
        [
            r"\bvolume[^;]{0,70}?(\d+(?:\.\d+)?)\s*(?:x|times)\b",
            r"\b(\d+(?:\.\d+)?)\s*(?:x|times)[^;]{0,50}\b(?:average\s+)?volume\b",
        ],
        "Volume filters need an explicit multiplier, for example '1.5 times average volume'.",
    )
    return int(window), multiplier


def _parse_average_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    matches: list[tuple[int, str, int]] = []
    for pattern, reversed_groups in (
        (r"\b(sma|ema|ma)\s*[- ]?(\d+)\b", False),
        (r"\b(\d+)\s*[- ]?(?:day|bar|session)?\s*(sma|ema|ma)\b", True),
    ):
        for match in re.finditer(pattern, normalized):
            indicator_type = match.group(2 if reversed_groups else 1)
            window = int(match.group(1 if reversed_groups else 2))
            matches.append((match.start(), indicator_type, window))
    unique_matches: list[tuple[str, int]] = []
    for _, indicator_type, window in sorted(matches):
        if (indicator_type, window) not in unique_matches:
            unique_matches.append((indicator_type, window))
    if len(unique_matches) < 2:
        raise ValueError("Include two explicit moving averages, for example 'SMA 10 crosses above SMA 50'.")
    explicit_types = {indicator_type for indicator_type, _ in unique_matches[:2] if indicator_type != "ma"}
    if len(explicit_types) > 1:
        raise ValueError("Local translation requires both averages to use the same SMA or EMA type.")
    fast_window, slow_window = sorted(window for _, window in unique_matches[:2])
    if fast_window == slow_window:
        raise ValueError("The fast and slow moving-average windows must be different.")
    template_id = "ema-crossover" if explicit_types == {"ema"} else "sma-crossover"
    strategy = _catalogue_strategy(template_id, {"fast_window": fast_window, "slow_window": slow_window}, risk)
    average_name = "EMA" if template_id == "ema-crossover" else "SMA"
    direction = "short" if re.search(r"\bshort\b", normalized) else "long"
    if direction == "short":
        configuration = deepcopy(strategy.configuration)
        configuration["direction"] = "short"
        configuration["entry"] = {"all": [{"left": "fast_average", "operator": "crosses_below", "right": "slow_average"}]}
        configuration["exit"] = {"any": [{"left": "fast_average", "operator": "crosses_above", "right": "slow_average"}]}
        strategy = DeclarativeStrategy(configuration)
    entry_relation = "above" if direction == "long" else "below"
    strategy = _with_description(
        strategy,
        f"Enter {direction} when {average_name}{fast_window} crosses {entry_relation} {average_name}{slow_window} and exit on the reverse crossover.",
    )
    if "volume" not in normalized:
        return strategy
    volume_window, volume_multiplier = _volume_parameters(normalized)
    configuration = deepcopy(strategy.configuration)
    configuration["indicators"].update(
        {
            "volume": {"type": "price", "source": "volume"},
            "average_volume": {"type": "volume_sma", "window": volume_window},
        }
    )
    configuration["entry"]["all"].append(
        {"left": "volume", "operator": "greater_than", "right": "average_volume", "right_multiplier": volume_multiplier}
    )
    configuration["description"] = (
        f"{configuration['description'].rstrip('.')} Require volume above {volume_multiplier:g} times its {volume_window}-session average."
    )
    return DeclarativeStrategy(configuration)


def _parse_rsi_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    window = _required_number(normalized, [r"\brsi\s*[- ]?(\d+)\b"], "RSI rules need an explicit window, for example RSI 14.")
    entry = _required_number(normalized, [r"\b(?:below|under)\s+(\d+(?:\.\d+)?)\b"], "RSI rules need an explicit oversold entry level.")
    exit_level = _required_number(normalized, [r"\b(?:above|over|through)\s+(\d+(?:\.\d+)?)\b"], "RSI rules need an explicit recovery exit level.")
    return _with_description(
        _catalogue_strategy("rsi-mean-reversion", {"window": int(window), "entry_level": entry, "exit_level": exit_level}, risk),
        f"Enter long when RSI{int(window)} falls below {entry:g} and exit after it recovers above {exit_level:g}.",
    )


def _parse_bollinger_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    window = _required_number(
        normalized,
        [r"\bboll(?:inger)?(?:\s+bands?)?\s*[- ]?(\d+)\b", r"\b(\d+)\s*[- ]?(?:day|bar|session)\s+boll(?:inger)?\b"],
        "Bollinger rules need an explicit band window.",
    )
    deviations = _required_number(
        normalized,
        [r"\b(\d+(?:\.\d+)?)\s*(?:standard\s+)?deviations?\b", r"\b(\d+(?:\.\d+)?)\s*(?:sigma|σ)\b"],
        "Bollinger rules need an explicit standard-deviation multiplier.",
    )
    return _with_description(
        _catalogue_strategy("bollinger-mean-reversion", {"window": int(window), "deviations": deviations}, risk),
        f"Enter long below the {int(window)}-session lower Bollinger Band at {deviations:g} standard deviations and exit through its middle band.",
    )


def _parse_donchian_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    windows = [int(value) for value in re.findall(r"\b(\d+)\s*[- ]?(?:day|bar|session)\b", normalized)]
    if len(windows) < 2:
        raise ValueError("Donchian rules need explicit entry and exit channel windows, for example 55-bar high and 20-bar low.")
    return _with_description(
        _catalogue_strategy("donchian-breakout", {"entry_window": windows[0], "exit_window": windows[1]}, risk),
        f"Enter long above the prior {windows[0]}-session high and exit below the prior {windows[1]}-session low.",
    )


def _parse_darvas_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    box_window = _required_number(
        normalized,
        [r"\bdarvas[^.;]{0,30}?(\d+)\s*[- ]?(?:day|bar|session)", r"\b(\d+)\s*[- ]?(?:day|bar|session)\s+darvas"],
        "Darvas rules need an explicit box window.",
    )
    confirmations = _required_number(
        normalized,
        [r"\b(?:after|with|require)?\s*(\d+)\s+(?:bar\s+)?confirmations?\b"],
        "Darvas rules need an explicit number of confirmation bars.",
    )
    volume_window, volume_multiplier = _volume_parameters(normalized)
    return _with_description(
        _catalogue_strategy(
            "darvas-volume-breakout",
            {
                "box_window": int(box_window),
                "confirmation_bars": int(confirmations),
                "volume_window": volume_window,
                "volume_multiplier": volume_multiplier,
            },
            risk,
        ),
        f"Enter long above a confirmed {int(box_window)}-session Darvas ceiling after {int(confirmations)} confirmation bars when volume exceeds {volume_multiplier:g} times its {volume_window}-session average; exit below the box floor.",
    )


def _parse_fibonacci_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    window = _required_number(
        normalized,
        [r"\b(\d+)\s*[- ]?(?:day|bar|session)\s+(?:rolling\s+)?swing", r"\bswing[^.;]{0,30}?(\d+)\s*[- ]?(?:day|bar|session)"],
        "Fibonacci rules need an explicit deterministic swing window.",
    )
    ratio = _required_number(
        normalized,
        [r"\b(?:fibonacci|fib)?\s*(\d+(?:\.\d+)?)\s*%\s+(?:retracement|resistance)", r"\b(0\.\d+)\s+(?:retracement|resistance)"],
        "Fibonacci rules need an explicit retracement ratio, for example 61.8%.",
    )
    ratio = ratio / 100 if ratio > 1 else ratio
    return _with_description(
        _catalogue_strategy("fibonacci-resistance-breakout", {"window": int(window), "ratio": ratio}, risk),
        f"Enter long through the {(ratio * 100):g}% Fibonacci resistance from the prior deterministic {int(window)}-session rolling swing and exit below that level.",
    )


def _parse_macd_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    match = re.search(r"\bmacd\s*(\d+)\s*[/,\-]\s*(\d+)\s*[/,\-]\s*(\d+)\b", normalized)
    if not match:
        raise ValueError("MACD rules need explicit fast, slow, and signal windows, for example MACD 12/26/9.")
    fast_window, slow_window, signal_window = (int(value) for value in match.groups())
    return _with_description(
        _catalogue_strategy("macd-trend", {"fast_window": fast_window, "slow_window": slow_window, "signal_window": signal_window}, risk),
        f"Enter long when MACD {fast_window}/{slow_window} crosses above its {signal_window}-session signal and exit on the reverse crossover.",
    )


def _parse_relative_strength_strategy(normalized: str, risk: dict[str, float]) -> DeclarativeStrategy:
    window = _required_number(
        normalized,
        [r"\b(\d+)\s*[- ]?(?:day|bar|session)\s+relative\s+strength", r"\brelative\s+strength[^.;]{0,30}?(\d+)\s*[- ]?(?:day|bar|session)"],
        "Relative-strength rules need an explicit comparison window.",
    )
    threshold = _required_number(
        normalized,
        [r"\b(?:exceeds?|above|outperforms?\s+by)\s+(\d+(?:\.\d+)?)\s*%"],
        "Relative-strength rules need an explicit outperformance threshold.",
    )
    return _with_description(
        _catalogue_strategy("benchmark-relative-strength", {"window": int(window), "entry_threshold": threshold}, risk),
        f"Enter long when the stock's {int(window)}-session return beats the selected reference by {threshold:g}% and exit when relative performance turns negative.",
    )


def _with_description(strategy: DeclarativeStrategy, description: str) -> DeclarativeStrategy:
    configuration = deepcopy(strategy.configuration)
    configuration["description"] = description
    return DeclarativeStrategy(configuration)


def _with_risk_description(strategy: DeclarativeStrategy, risk: dict[str, float]) -> DeclarativeStrategy:
    if not risk:
        return strategy
    controls: list[str] = []
    if "stop_loss_percent" in risk:
        controls.append(f"a {risk['stop_loss_percent']:g}% fixed stop loss")
    if "take_profit_percent" in risk:
        controls.append(f"a {risk['take_profit_percent']:g}% take-profit target")
    if "trailing_stop_percent" in risk:
        controls.append(f"a {risk['trailing_stop_percent']:g}% trailing stop from the most favorable close")
    if "atr_stop_multiple" in risk:
        controls.append(f"a {risk['atr_stop_multiple']:g}× ATR stop")
    if "max_holding_days" in risk:
        controls.append(f"a {risk['max_holding_days']:g}-session maximum holding period")
    if not controls:
        return strategy
    configuration = deepcopy(strategy.configuration)
    configuration["description"] = f"{configuration['description'].rstrip('.')} Apply {'; '.join(controls)}."
    return DeclarativeStrategy(configuration)


def _validate_criteria(criteria: dict[str, Any], indicators: set[str], operators: set[str]) -> None:
    if not isinstance(criteria, dict) or len(criteria) != 1:
        raise ValueError("Criteria must contain exactly one 'all' or 'any' group.")
    group, rules = next(iter(criteria.items()))
    if group not in {"all", "any"} or not isinstance(rules, list) or not rules:
        raise ValueError("Criteria must contain a non-empty 'all' or 'any' rule list.")
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("left") not in indicators:
            raise ValueError("Every rule must reference a defined left indicator.")
        if rule.get("operator") not in operators:
            raise ValueError(f"Unsupported rule operator '{rule.get('operator')}'.")
        right = rule.get("right")
        if not isinstance(right, (int, float)) and right not in indicators:
            raise ValueError("Rule right-hand side must be a defined indicator or number.")
        multiplier = float(rule.get("right_multiplier", 1.0))
        if multiplier <= 0 or multiplier > 100:
            raise ValueError("Rule right_multiplier must be greater than 0 and at most 100.")
        if "right_multiplier" in rule:
            rule["right_multiplier"] = multiplier


def _evaluate_criteria(criteria: dict[str, Any], frame: pd.DataFrame) -> pd.Series:
    group, rules = next(iter(criteria.items()))
    signals = [_evaluate_rule(rule, frame) for rule in rules]
    result = signals[0]
    for signal in signals[1:]:
        result = result & signal if group == "all" else result | signal
    return result


def _evaluate_rule(rule: dict[str, Any], frame: pd.DataFrame) -> pd.Series:
    left = frame[rule["left"]]
    right = frame[rule["right"]] if isinstance(rule["right"], str) else float(rule["right"])
    right = right * float(rule.get("right_multiplier", 1.0))
    operator = rule["operator"]
    if operator == "crosses_above":
        return (left > right) & (left.shift(1) <= (right.shift(1) if isinstance(right, pd.Series) else right))
    if operator == "crosses_below":
        return (left < right) & (left.shift(1) >= (right.shift(1) if isinstance(right, pd.Series) else right))
    return {"greater_than": left > right, "less_than": left < right, "greater_or_equal": left >= right, "less_or_equal": left <= right}[operator]


def _criteria_text(criteria: dict[str, Any]) -> str:
    group, rules = next(iter(criteria.items()))
    joiner = " AND " if group == "all" else " OR "
    return joiner.join(f"{rule['left']} {rule['operator'].replace('_', ' ')} {rule.get('right_multiplier', 1):g} × {rule['right']}" if rule.get("right_multiplier", 1) != 1 else f"{rule['left']} {rule['operator'].replace('_', ' ')} {rule['right']}" for rule in rules)


def _trades(frame: pd.DataFrame) -> list[dict[str, Any]]:
    trades, open_trade, previous_position = [], None, 0
    for index, row in frame.iterrows():
        position = int(row.position)
        if previous_position and position != previous_position and open_trade:
            multiplier, exit_price = (1 if previous_position == 1 else -1), float(row.close)
            pnl = (exit_price - open_trade["entryPrice"]) * multiplier
            trades.append({**open_trade, "status": "Closed", "exitDate": index.strftime("%Y-%m-%d"), "exitPrice": round(exit_price, 2), "pnl": round(pnl, 2), "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2)})
            open_trade = None
        if position and position != previous_position:
            open_trade = {"entryDate": index.strftime("%Y-%m-%d"), "entryPrice": round(float(row.close), 2), "side": "LONG" if position == 1 else "SHORT"}
        previous_position = position
    if open_trade:
        final_index, final_price = frame.index[-1], float(frame.iloc[-1].close)
        multiplier = 1 if previous_position == 1 else -1
        pnl = (final_price - open_trade["entryPrice"]) * multiplier
        trades.append({**open_trade, "status": "Open", "exitDate": None, "exitPrice": round(final_price, 2), "asOfDate": final_index.strftime("%Y-%m-%d"), "pnl": round(pnl, 2), "pnlPercent": round(pnl / open_trade["entryPrice"] * 100, 2)})
    return trades


def run_backtest(history: pd.DataFrame, spy_history: pd.DataFrame, strategy: Strategy) -> dict[str, Any]:
    from ..backtesting.engine import run_backtest as execute_backtest

    return execute_backtest(history, spy_history, strategy)
