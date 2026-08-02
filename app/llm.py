from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .strategy import Strategy, StrategyFactory, parse_strategy

load_dotenv()


@dataclass(frozen=True)
class Translation:
    strategy: Strategy
    provider: str
    yaml_config: str


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
Only express logic possible with this schema. Preserve every explicit threshold and window from the instruction."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def translate(self, instruction: str) -> Translation:
        if not self.configured:
            strategy = parse_strategy(instruction)
            return Translation(strategy=strategy, provider="deterministic_fallback", yaml_config=strategy.to_yaml())
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=instruction,
                config=types.GenerateContentConfig(system_instruction=self.SYSTEM_PROMPT),
            )
            raw_yaml = response.text.strip().removeprefix("```yaml").removeprefix("```").removesuffix("```").strip()
            strategy = StrategyFactory.from_yaml(raw_yaml)
            return Translation(strategy=strategy, provider="google_ai_studio", yaml_config=strategy.to_yaml())
        except Exception as error:
            raise ValueError(f"Google AI Studio could not translate the strategy: {error}") from error

    def status(self) -> dict[str, str | bool]:
        return {"configured": self.configured, "model": self.model, "provider": "Google AI Studio", "format": "GBB Strategy YAML v1"}
