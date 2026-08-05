from __future__ import annotations

import os

from ...settings import LLMSettings
from .base import ProviderUnavailable


class AnthropicProvider:
    key = "anthropic"
    display_name = "Anthropic Claude"

    def __init__(self, settings: LLMSettings) -> None:
        self.model = settings.model
        self.timeout_seconds = settings.timeout_ms / 1000
        self.temperature = settings.temperature
        self.max_output_tokens = settings.max_output_tokens
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, instruction: str, system_prompt: str) -> str:
        if not self.configured:
            raise ProviderUnavailable("Anthropic API key is not configured")
        try:
            from anthropic import Anthropic
        except ImportError as error:
            raise ProviderUnavailable("Anthropic SDK is not installed; run pip install -e '.[llm-anthropic]'") from error
        client = Anthropic(api_key=self.api_key, timeout=self.timeout_seconds)
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": instruction}],
        )
        response_text = "".join(block.text for block in response.content if block.type == "text")
        if not response_text:
            raise ProviderUnavailable("Anthropic Claude returned an empty response")
        return response_text
