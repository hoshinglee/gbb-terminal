from gbb_terminal.llm.providers import create_completion_provider
from gbb_terminal.settings import LLMSettings, Settings


def test_settings_loads_selected_provider_from_conf_file(tmp_path):
    config_directory = tmp_path / "conf"
    config_directory.mkdir()
    (config_directory / "app.yaml").write_text(
        """\
paths:
  database_path: local/research.duckdb
llm:
  provider: claude
  timeout_ms: 12000
  providers:
    anthropic:
      model: claude-test-model
""",
        encoding="utf-8",
    )

    configuration = Settings.from_sources(project_root=tmp_path, environment={})

    assert configuration.database_path == tmp_path / "local" / "research.duckdb"
    assert configuration.frontend_static_directory == tmp_path / "app" / "static"
    assert configuration.frontend_legacy_index == tmp_path / "app" / "index.html"
    assert configuration.frontend_react_index == tmp_path / "app" / "static" / "react" / "index.html"
    assert configuration.frontend_index == tmp_path / "app" / "index.html"
    assert configuration.estimate_fixture_path == tmp_path / "conf" / "estimates.json"
    assert configuration.llm.provider == "anthropic"
    assert configuration.llm.model == "claude-test-model"
    assert configuration.llm.timeout_ms == 12000


def test_environment_overrides_conf_file(tmp_path):
    config_path = tmp_path / "custom.yaml"
    config_path.write_text("llm:\n  provider: google\n", encoding="utf-8")

    configuration = Settings.from_sources(
        project_root=tmp_path,
        environment={"GBB_CONFIG_PATH": str(config_path), "GBB_LLM_PROVIDER": "openai", "OPENAI_MODEL": "openai-test-model"},
    )

    assert configuration.llm.provider == "openai"
    assert configuration.llm.model == "openai-test-model"


def test_settings_prefers_built_react_index_and_keeps_legacy_fallback(tmp_path):
    react_directory = tmp_path / "app" / "static" / "react"
    react_directory.mkdir(parents=True)
    (react_directory / "index.html").write_text("<div id='root'></div>", encoding="utf-8")

    configuration = Settings.from_sources(project_root=tmp_path, environment={})

    assert configuration.frontend_index == react_directory / "index.html"
    assert configuration.frontend_legacy_index == tmp_path / "app" / "index.html"


def test_provider_factory_selects_anthropic_without_importing_sdk(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    provider = create_completion_provider(
        LLMSettings(provider="anthropic", model="claude-test-model", timeout_ms=1000, temperature=0.1, max_output_tokens=100)
    )

    assert provider.key == "anthropic"
    assert provider.display_name == "Anthropic Claude"
    assert provider.configured is True
