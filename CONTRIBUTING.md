# Contributing to GBB Terminal

GBB Terminal welcomes focused contributions that improve transparent research for hobbyist US equity and options investors.

## Development setup

```bash
conda activate gbbterminal
pip install -e ".[dev]"
cd app/web
npm install
npm run build
cd ../..
uvicorn gbb_terminal.api.main:app --reload
```

For natural-language translation, copy `conf/app.example.yaml` to `conf/app.yaml` and configure one provider key in `.env`. The OpenAI and Anthropic SDKs are optional: `pip install -e ".[dev,llm-openai]"` or `pip install -e ".[dev,llm-anthropic]"`.

Run validation before opening a pull request:

```bash
pytest
ruff check src tests
node --check app/static/app.js
cd app/web && npm run typecheck && npm run test:run && npm run build
```

## Contribution rules

- Keep the application free, local-first, and useful without paid data.
- Treat strategy results as research evidence, not performance promises.
- Never execute generated or imported Python. Strategies must use validated models and registered functions.
- Preserve point-in-time timestamps (`observation_timestamp`, `known_at`, and `retrieved_at`) for external data.
- Label theoretical option simulation clearly; do not present it as historical contract backtesting.
- Add focused tests for domain behavior, migrations, API contracts, and bug fixes.
- Do not commit `.env`, DuckDB files, downloaded datasets, or runtime logs.

See [`docs/strategy-plugin-guide.md`](docs/strategy-plugin-guide.md) before adding a strategy family or indicator.
