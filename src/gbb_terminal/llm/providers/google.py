from __future__ import annotations

import os

from ...settings import LLMSettings
from .base import ProviderUnavailable


class GoogleAIStudioProvider:
    key = "google"
    display_name = "Google AI Studio"

    def __init__(self, settings: LLMSettings) -> None:
        self.model = settings.model
        self.timeout_ms = settings.timeout_ms
        self.temperature = settings.temperature
        self.max_output_tokens = settings.max_output_tokens
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, instruction: str, system_prompt: str) -> str:
        if not self.configured:
            raise ProviderUnavailable("Google AI Studio API key is not configured")
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise ProviderUnavailable("Google AI Studio SDK is not installed") from error
        client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=self.timeout_ms))
        response = client.models.generate_content(
            model=self.model,
            contents=instruction,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise ProviderUnavailable("Google AI Studio returned an empty response")
        return response.text
