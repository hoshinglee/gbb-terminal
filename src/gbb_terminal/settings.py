from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root / path


def _load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        contents = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid configuration file at {path}: {error}") from error
    if contents is None:
        return {}
    if not isinstance(contents, dict):
        raise ValueError(f"Configuration file at {path} must contain a mapping.")
    return contents


def _config_value(configuration: Mapping[str, object], dotted_key: str, default: object) -> object:
    value: object = configuration
    for key in dotted_key.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return default
        value = value[key]
    return value


def _value(environment: Mapping[str, str], name: str, configuration: Mapping[str, object], key: str, default: object) -> object:
    return environment.get(name, _config_value(configuration, key, default))


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    timeout_ms: int
    temperature: float
    max_output_tokens: int


@dataclass(frozen=True)
class Settings:
    project_root: Path
    config_directory: Path
    config_path: Path
    frontend_directory: Path
    database_path: Path
    log_directory: Path
    refresh_interval_seconds: int
    data_contact: str
    llm: LLMSettings

    @classmethod
    def from_sources(
        cls,
        project_root: Path = PROJECT_ROOT,
        environment: Mapping[str, str] | None = None,
    ) -> "Settings":
        source_environment = os.environ if environment is None else environment
        root = project_root.resolve()
        config_directory = _resolve_path(source_environment.get("GBB_CONFIG_DIRECTORY", "conf"), root)
        config_path = _resolve_path(source_environment.get("GBB_CONFIG_PATH", str(config_directory / "app.yaml")), root)
        configuration = _load_config(config_path)

        provider = str(_value(source_environment, "GBB_LLM_PROVIDER", configuration, "llm.provider", "google")).strip().lower()
        provider = {"google_ai_studio": "google", "claude": "anthropic"}.get(provider, provider)
        provider_models = {
            "google": ("GEMINI_MODEL", "google", "gemini-3.6-flash"),
            "openai": ("OPENAI_MODEL", "openai", "gpt-5"),
            "anthropic": ("ANTHROPIC_MODEL", "anthropic", "claude-sonnet-4-0"),
        }
        if provider not in provider_models:
            raise ValueError("GBB_LLM_PROVIDER must be one of: google, openai, anthropic.")
        provider_model_key, provider_config_key, default_model = provider_models[provider]
        configured_model = _config_value(configuration, f"llm.providers.{provider_config_key}.model", default_model)
        model = str(source_environment.get("GBB_LLM_MODEL", source_environment.get(provider_model_key, configured_model))).strip()
        configured_timeout = _config_value(configuration, "llm.timeout_ms", 45000)
        timeout_ms = int(source_environment.get("GBB_LLM_TIMEOUT_MS", source_environment.get("GEMINI_TIMEOUT_MS", configured_timeout)))

        return cls(
            project_root=root,
            config_directory=config_directory,
            config_path=config_path,
            frontend_directory=_resolve_path(str(_value(source_environment, "GBB_FRONTEND_DIRECTORY", configuration, "paths.frontend_directory", "app")), root),
            database_path=_resolve_path(str(_value(source_environment, "GBB_DATABASE_PATH", configuration, "paths.database_path", "data/gbb_terminal.duckdb")), root),
            log_directory=_resolve_path(str(_value(source_environment, "GBB_LOG_DIRECTORY", configuration, "paths.log_directory", "log")), root),
            refresh_interval_seconds=int(_value(source_environment, "GBB_REFRESH_INTERVAL_SECONDS", configuration, "app.refresh_interval_seconds", 900)),
            data_contact=str(_value(source_environment, "GBB_DATA_CONTACT", configuration, "app.data_contact", "your-email@example.com")),
            llm=LLMSettings(
                provider=provider,
                model=model,
                timeout_ms=timeout_ms,
                temperature=float(_value(source_environment, "GBB_LLM_TEMPERATURE", configuration, "llm.temperature", 0.1)),
                max_output_tokens=int(_value(source_environment, "GBB_LLM_MAX_OUTPUT_TOKENS", configuration, "llm.max_output_tokens", 1200)),
            ),
        )


settings = Settings.from_sources()
