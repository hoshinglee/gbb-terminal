from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from .strategy import Strategy, StrategyFactory, parse_strategy

load_dotenv()


@dataclass(frozen=True)
class Translation:
    strategy: Strategy
    provider: str


class GoogleAIStrategyTranslator:
    """Translates an instruction into a factory-supported strategy definition."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def translate(self, instruction: str) -> Translation:
        if not self.configured:
            return Translation(strategy=parse_strategy(instruction), provider="deterministic_fallback")
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "Convert this trading instruction into JSON only. Support only a moving-average crossover. "
                    "Return strategy_type='moving_average_crossover', direction ('long' or 'short'), and parameters "
                    "with integer fast_window and slow_window. Do not invent indicator values. Instruction: " + instruction
                ),
            )
            raw_definition = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            definition: dict[str, Any] = json.loads(raw_definition)
            return Translation(strategy=StrategyFactory.create(definition), provider="google_ai_studio")
        except Exception as error:
            raise ValueError(f"Google AI Studio could not translate the strategy: {error}") from error

    def status(self) -> dict[str, str | bool]:
        return {"configured": self.configured, "model": self.model, "provider": "Google AI Studio"}
