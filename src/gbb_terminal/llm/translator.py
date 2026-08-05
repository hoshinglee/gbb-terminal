from __future__ import annotations

import os
import re
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

from ..strategy.factory import Strategy, StrategyFactory, parse_strategy

load_dotenv()


@dataclass(frozen=True)
class Translation:
    strategy: Strategy
    provider: str
    yaml_config: str
    normalized_instruction: str
    clarifications: list[str]
    needs_confirmation: bool


class GoogleAIStrategyTranslator:
    """Uses Google AI Studio to translate natural language into the safe strategy YAML DSL."""

    SYSTEM_PROMPT = """You translate trading instructions into GBB Strategy YAML version 1.
Return YAML only, without Markdown fences. Never return Python or executable code.
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
Required schema:
version: 1
name: concise strategy name
description: intuitive business description
direction: long or short
indicators:
  alias_name:
    type: sma
    source: close
    window: 5
entry:
  all:
    - left: alias_name
      operator: crosses_above
      right: another_alias_or_number
exit:
  any:
    - left: alias_name
      operator: crosses_below
      right: another_alias_or_number
      right_multiplier: optional positive multiplier applied to right
Optional risk settings:
risk:
  stop_loss_percent: positive percentage
  take_profit_percent: positive percentage
  trailing_stop_percent: positive percentage
  atr_stop_multiple: positive ATR multiple
  atr_window: optional ATR window
  max_holding_days: positive session count
Only express logic possible with this schema. Preserve every explicit threshold and window from the instruction.
Never invent a missing threshold, indicator window, multiplier, or risk percentage."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.timeout_ms = int(os.getenv("GEMINI_TIMEOUT_MS", "45000"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def translate(self, instruction: str) -> Translation:
        if not self.configured:
            strategy = parse_strategy(instruction)
            clarifications = ambiguity_notes(instruction, strategy)
            if re.search(r"\b(volume|rsi|stop loss|loss threshold|take profit)\b", instruction, re.IGNORECASE):
                clarifications.append("Google AI Studio is not configured; the deterministic fallback only translated the moving-average crossover.")
            return Translation(strategy=strategy, provider="deterministic_fallback", yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=clarifications, needs_confirmation=bool(clarifications))
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms))
            response = client.models.generate_content(
                model=self.model,
                contents=instruction,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=1200,
                ),
            )
            raw_yaml = response.text.strip().removeprefix("```yaml").removeprefix("```").removesuffix("```").strip()
            strategy, repair_notes = validated_model_strategy(raw_yaml)
            clarifications = [*ambiguity_notes(instruction, strategy), *repair_notes]
            return Translation(strategy=strategy, provider="google_ai_studio", yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=clarifications, needs_confirmation=True)
        except Exception as error:
            try:
                strategy = parse_strategy(instruction)
            except ValueError:
                raise ValueError(f"Google AI Studio could not translate the strategy: {provider_failure_reason(error)}") from error
            clarifications = ambiguity_notes(instruction, strategy)
            clarifications.append(f"Google AI Studio was unavailable ({provider_failure_reason(error)}); the proposed fallback only includes the moving-average crossover.")
            return Translation(strategy=strategy, provider="deterministic_fallback_after_google_error", yaml_config=strategy.to_yaml(), normalized_instruction=strategy.spec().description, clarifications=list(dict.fromkeys(clarifications)), needs_confirmation=True)

    def status(self) -> dict[str, str | bool | int]:
        return {"configured": self.configured, "model": self.model, "provider": "Google AI Studio", "format": "GBB Strategy YAML v1", "timeoutMs": self.timeout_ms}


def ambiguity_notes(instruction: str, strategy: Strategy) -> list[str]:
    normalized = instruction.lower()
    notes: list[str] = []
    if re.search(r"\b(high|strong|significant|unusual)\s+(daily\s+)?volume\b", normalized) and not re.search(r"\b\d+(?:\.\d+)?\s*(?:x|times|%)\b", normalized):
        notes.append("High volume has no explicit multiplier; review the proposed volume comparison.")
    if "loss threshold" in normalized and not re.search(r"\d+(?:\.\d+)?\s*%", normalized):
        notes.append("The loss threshold has no percentage; the proposal does not invent one.")
    if any(term in normalized for term in ("quickly", "soon", "strong trend", "weak trend")):
        notes.append("The timing or trend strength is subjective; review the exact indicators and windows.")
    risk = strategy.spec().parameters.get("risk", {})
    if re.search(r"\b(stop loss|loss threshold|max(?:imum)? loss)\b", normalized) and not risk:
        notes.append("The instruction mentions loss control, but no valid numeric stop-loss rule was produced.")
    return list(dict.fromkeys(notes))


def provider_failure_reason(error: Exception) -> str:
    message = str(error).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        return "provider quota exceeded"
    if "timeout" in message or "timed out" in message:
        return "provider timeout"
    if "invalid_argument" in message:
        return "provider rejected the request configuration"
    return "provider request failed"


def validated_model_strategy(raw_yaml: str) -> tuple[Strategy, list[str]]:
    try:
        return StrategyFactory.from_yaml(raw_yaml), []
    except ValueError as validation_error:
        configuration = yaml.safe_load(raw_yaml)
        if not isinstance(configuration, dict):
            raise validation_error
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
