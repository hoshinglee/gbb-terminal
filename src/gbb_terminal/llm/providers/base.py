from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProviderUnavailable(RuntimeError):
    """Raised when an optional LLM provider cannot serve a request."""


class CompletionProvider(Protocol):
    key: str
    display_name: str
    model: str

    @property
    def configured(self) -> bool: ...

    def generate(self, instruction: str, system_prompt: str) -> str: ...


@dataclass(frozen=True)
class ProviderDetails:
    key: str
    display_name: str
    model: str
    configured: bool
