from __future__ import annotations

import json

import pytest

from gbb_terminal.llm.translator import StrategyTranslator, validated_model_strategy
from gbb_terminal.settings import LLMSettings


class StubProvider:
    key = "stub"
    display_name = "Stub Provider"
    model = "stub-model"

    def __init__(self, response: str | Exception, *, configured: bool = True) -> None:
        self.response = response
        self.configured = configured

    def generate(self, instruction: str, system_prompt: str) -> str:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def translator(provider: StubProvider) -> StrategyTranslator:
    return StrategyTranslator(
        LLMSettings(provider="google", model="stub-model", timeout_ms=1000, temperature=0.0, max_output_tokens=500),
        provider=provider,
    )


def test_provider_json_is_validated_and_server_serializes_compatibility_yaml():
    definition = {
        "version": 1,
        "name": "volume confirmed trend",
        "description": "Long when SMA 10 crosses above SMA 50 and protect gains with a trailing stop",
        "direction": "long",
        "indicators": {
            "fast": {"type": "sma", "source": "close", "window": 10},
            "slow": {"type": "sma", "source": "close", "window": 50},
        },
        "entry": {"all": [{"left": "fast", "operator": "crosses_above", "right": "slow"}]},
        "exit": {"any": [{"left": "fast", "operator": "crosses_below", "right": "slow"}]},
        "risk": {"trailing_stop_percent": 8},
    }

    result = translator(StubProvider(json.dumps(definition))).translate("Use SMA 10/50 with an 8% trailing stop.")

    assert result.provider == "Stub Provider"
    assert result.strategy.spec().parameters["risk"]["trailing_stop_percent"] == 8
    assert "trailing_stop_percent: 8.0" in result.yaml_config
    assert "```" not in result.yaml_config


def test_invalid_provider_response_falls_back_without_dropping_explicit_rules():
    result = translator(StubProvider(RuntimeError("429 RESOURCE_EXHAUSTED"))).translate(
        "Long when SMA 10 crosses above SMA 50 with volume above 1.5 times its 20-day average; "
        "exit on the reverse crossover or a 7% trailing stop."
    )
    parameters = result.strategy.spec().parameters

    assert result.provider == "deterministic_fallback_after_stub_error"
    assert parameters["risk"]["trailing_stop_percent"] == 7
    assert parameters["indicators"]["average_volume"]["window"] == 20
    assert len(parameters["entry"]["all"]) == 2
    assert any("quota exceeded" in note for note in result.clarifications)


def test_local_translation_supports_explicit_rsi_and_trailing_stop():
    result = translator(StubProvider("", configured=False)).translate(
        "Buy when RSI 14 falls below 30; exit above 55 with a 6% trailing stop."
    )

    assert result.strategy.spec().name == "RSI Mean Reversion"
    assert result.strategy.spec().parameters["risk"]["trailing_stop_percent"] == 6
    assert result.needs_confirmation is True


def test_local_translation_preserves_short_average_direction():
    result = translator(StubProvider("", configured=False)).translate(
        "Short when EMA 5 crosses below EMA 20 and exit on the reverse crossover with a 5% trailing stop."
    )

    specification = result.strategy.spec()
    assert specification.direction == "short"
    assert specification.parameters["entry"]["all"][0]["operator"] == "crosses_below"
    assert specification.parameters["risk"]["trailing_stop_percent"] == 5


def test_local_translation_supports_the_darvas_quick_start():
    result = translator(StubProvider("", configured=False)).translate(
        "Enter a 20-bar Darvas breakout after 3 confirmations when volume is 1.5 times its 20-day average."
    )

    parameters = result.strategy.spec().parameters
    assert parameters["indicators"]["box_high"] == {"type": "darvas_high", "window": 20, "confirmation_bars": 3}
    assert parameters["entry"]["all"][1]["right_multiplier"] == 1.5


def test_model_payload_must_be_json_not_yaml():
    with pytest.raises(ValueError, match="invalid strategy JSON"):
        validated_model_strategy("version: 1\nname: Unsafe YAML")
