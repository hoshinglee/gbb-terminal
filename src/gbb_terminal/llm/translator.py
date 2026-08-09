from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..settings import LLMSettings, settings
from ..strategy.factory import Strategy, StrategyFactory, parse_strategy
from .providers import CompletionProvider, create_completion_provider


@dataclass(frozen=True)
class Translation:
    strategy: Strategy
    provider: str
    yaml_config: str
    normalized_instruction: str
    clarifications: list[str]
    needs_confirmation: bool


class StrategyTranslator:
    """Translates natural language into a validated declarative strategy."""

    SYSTEM_PROMPT = """You translate trading instructions into GBB Strategy JSON version 1.
Return exactly one JSON object without Markdown fences. Never return Python, YAML, expressions, or executable code.
Available indicator types:
- price: source is open, high, low, close, or volume
- sma: source and integer window
- ema: source and integer window
- rsi: source and integer window
- volume_sma: integer window
- rolling_std, bollinger_upper, bollinger_lower: source, integer window, and optional deviations
- macd and macd_signal: fast_window, slow_window, and signal_window
- atr, donchian_high, donchian_low: integer window
- darvas_high and darvas_low: integer window and confirmation_bars
- obv and gap: no parameters
- zscore and volatility: source and integer window
- fibonacci_level: integer window and ratio between 0 and 1; never use manually selected historical anchors
- relative_strength: integer window and requires aligned benchmark data
Available operators: crosses_above, crosses_below, greater_than, less_than, greater_or_equal, less_or_equal.
Required JSON shape:
{
  "version": 1,
  "name": "Concise Strategy Name",
  "description": "Intuitive business description.",
  "direction": "long",
  "indicators": {
    "alias_name": {"type": "sma", "source": "close", "window": 5}
  },
  "entry": {
    "all": [
      {"left": "alias_name", "operator": "crosses_above", "right": "another_alias_or_number"}
    ]
  },
  "exit": {
    "any": [
      {"left": "alias_name", "operator": "crosses_below", "right": "another_alias_or_number"}
    ]
  },
  "risk": {}
}
The optional right_multiplier is a positive number applied to the right-hand indicator.
Optional risk settings:
stop_loss_percent, take_profit_percent, trailing_stop_percent, atr_stop_multiple, atr_window, and max_holding_days.
Only express logic possible with this schema. Preserve every explicit threshold and window from the instruction.
Never invent a missing threshold, indicator window, multiplier, or risk percentage."""

    def __init__(self, configuration: LLMSettings | None = None, provider: CompletionProvider | None = None) -> None:
        self.configuration = configuration or settings.llm
        self.provider_client = provider or create_completion_provider(self.configuration)

    @property
    def configured(self) -> bool:
        return self.provider_client.configured

    def translate(self, instruction: str) -> Translation:
        if not self.configured:
            strategy = parse_strategy(instruction)
            clarifications = ambiguity_notes(instruction, strategy)
            clarifications.append(
                f"{self.provider_client.display_name} is not configured; the displayed proposal was translated locally from explicit values."
            )
            return Translation(strategy=strategy, provider="deterministic_fallback", yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=clarifications, needs_confirmation=bool(clarifications))
        try:
            raw_json = self.provider_client.generate(instruction, self.SYSTEM_PROMPT)
            strategy, repair_notes = validated_model_strategy(raw_json)
            clarifications = [*ambiguity_notes(instruction, strategy), *repair_notes]
            return Translation(strategy=strategy, provider=self.provider_client.display_name, yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=clarifications, needs_confirmation=True)
        except Exception as error:
            try:
                strategy = parse_strategy(instruction)
            except ValueError as fallback_error:
                raise ValueError(
                    f"{self.provider_client.display_name} could not translate the strategy ({provider_failure_reason(error)}). "
                    f"Local translation also needs clarification: {fallback_error}"
                ) from error
            clarifications = ambiguity_notes(instruction, strategy)
            clarifications.append(
                f"{self.provider_client.display_name} was unavailable ({provider_failure_reason(error)}); the displayed proposal was translated locally from explicit values."
            )
            return Translation(strategy=strategy, provider=f"deterministic_fallback_after_{self.provider_client.key}_error", yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=list(dict.fromkeys(clarifications)), needs_confirmation=True)

    def status(self) -> dict[str, str | bool | int]:
        return {
            "configured": self.configured,
            "model": self.provider_client.model,
            "provider": self.provider_client.display_name,
            "providerKey": self.provider_client.key,
            "format": "GBB Strategy JSON v1",
            "timeoutMs": self.configuration.timeout_ms,
        }


# Kept for integrations using the original Google-only class name.
GoogleAIStrategyTranslator = StrategyTranslator


def ambiguity_notes(instruction: str, strategy: Strategy) -> list[str]:
    normalized = instruction.lower()
    notes: list[str] = []
    if re.search(r"\b(high|strong|significant|unusual)\s+(daily\s+)?volume\b", normalized) and not re.search(r"\b\d+(?:\.\d+)?\s*(?:x|times|%)\b", normalized):
        notes.append("High volume has no explicit multiplier; review the proposed volume comparison.")
    if re.search(r"\b(loss threshold|stop loss|trailing stop|take profit|profit target)\b", normalized) and not re.search(r"\d+(?:\.\d+)?\s*%", normalized):
        notes.append("The requested risk control has no percentage; the proposal does not invent one.")
    if any(term in normalized for term in ("quickly", "soon", "strong trend", "weak trend")):
        notes.append("The timing or trend strength is subjective; review the exact indicators and windows.")
    risk = strategy.spec().parameters.get("risk", {})
    if re.search(r"\b(stop loss|trailing stop|loss threshold|max(?:imum)? loss|take profit|profit target)\b", normalized) and not risk:
        notes.append("The instruction mentions risk control, but no valid numeric risk rule was produced.")
    return list(dict.fromkeys(notes))


def provider_failure_reason(error: Exception) -> str:
    message = str(error).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        return "provider quota exceeded"
    if "timeout" in message or "timed out" in message:
        return "provider timeout"
    if "invalid_argument" in message:
        return "provider rejected the request configuration"
    if "not found" in message or "404" in message:
        return "configured model was not found"
    if "unavailable" in message or "503" in message or "502" in message or "500" in message:
        return "provider temporarily unavailable"
    return "provider request failed"


def validated_model_strategy(raw_json: str) -> tuple[Strategy, list[str]]:
    cleaned = raw_json.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    first_object, last_object = cleaned.find("{"), cleaned.rfind("}")
    if first_object >= 0 and last_object > first_object:
        cleaned = cleaned[first_object : last_object + 1]
    try:
        configuration = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("The provider returned invalid strategy JSON.") from error
    if not isinstance(configuration, dict):
        raise ValueError("The provider strategy JSON must contain one object.")
    try:
        return StrategyFactory.create(configuration), []
    except ValueError as validation_error:
        exit_rules = configuration.get("exit", {})
        entry_rules = configuration.get("entry", {})
        exit_is_empty = not isinstance(exit_rules, dict) or not any(exit_rules.values())
        candidate_rules = next(iter(entry_rules.values()), []) if isinstance(entry_rules, dict) else []
        crossover = next((rule for rule in candidate_rules if isinstance(rule, dict) and rule.get("operator") in {"crosses_above", "crosses_below"}), None)
        if not exit_is_empty or crossover is None:
            raise validation_error
        reverse_operator = "crosses_below" if crossover["operator"] == "crosses_above" else "crosses_above"
        configuration["exit"] = {"any": [{"left": crossover["left"], "operator": reverse_operator, "right": crossover["right"]}]}
        description = str(configuration.get("description", "Proposed crossover strategy")).rstrip(". ")
        configuration["description"] = f"{description}. Exit on the reverse crossover because no executable exit threshold was supplied."
        strategy = StrategyFactory.create(configuration)
        return strategy, ["The proposed exit uses the reverse crossover because the instruction did not provide an executable numeric loss threshold."]
