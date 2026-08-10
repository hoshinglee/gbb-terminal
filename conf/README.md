# Local Configuration

Copy `app.example.yaml` to `app.yaml` to configure a local GBB Terminal installation. The real file is ignored by Git because it represents one machine's runtime preferences.

Use this file for non-secret paths, refresh behaviour, and LLM provider/model settings. Put API keys only in the project-root `.env` file:

```dotenv
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

Configuration precedence is: process environment variables, `.env`, `conf/app.yaml`, then built-in defaults. `GBB_CONFIG_PATH` can point to a different YAML file, and paths are always resolved relative to the project root.

Optional analyst-estimate development data can be placed in ignored `conf/estimates.json` or selected with `GBB_ESTIMATE_FIXTURE_PATH`. The file must follow the provider-neutral contract documented in `docs/analyst-estimates.md`; it is manual local data, not scraped consensus coverage.
