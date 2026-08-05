from __future__ import annotations

from ...settings import LLMSettings
from .anthropic import AnthropicProvider
from .base import CompletionProvider
from .google import GoogleAIStudioProvider
from .openai import OpenAIProvider


def create_completion_provider(settings: LLMSettings) -> CompletionProvider:
    providers = {
        "google": GoogleAIStudioProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }
    try:
        return providers[settings.provider](settings)
    except KeyError as error:
        raise ValueError(f"Unsupported LLM provider: {settings.provider}") from error
