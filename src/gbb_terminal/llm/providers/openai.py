from __future__ import annotations

import os

from ...settings import LLMSettings
from .base import ProviderUnavailable


class OpenAIProvider:
    key = "openai"
    display_name = "OpenAI"

    def __init__(self, settings: LLMSettings) -> None:
        self.model = settings.model
        self.timeout_seconds = settings.timeout_ms / 1000
        self.temperature = settings.temperature
        self.max_output_tokens = settings.max_output_tokens
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, instruction: str, system_prompt: str) -> str:
        if not self.configured:
            raise ProviderUnavailable("OpenAI API key is not configured")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ProviderUnavailable("OpenAI SDK is not installed; run pip install -e '.[llm-openai]'") from error
        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        response = client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=instruction,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        if not response.output_text:
            raise ProviderUnavailable("OpenAI returned an empty response")
        return response.output_text
