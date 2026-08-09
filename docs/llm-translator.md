# LLM Strategy Translator

Source: `src/gbb_terminal/llm/translator.py`

## Business definition

The translator turns a trader's natural-language intent into a strict GBB Strategy JSON proposal. It is a translation layer only; `StrategyFactory` remains the authority that accepts or rejects the output.

## Functions

| Name | Definition |
| --- | --- |
| `StrategyTranslator.translate` | Sends the instruction and constrained schema to the selected provider, validates the returned JSON object, and supplies confirmation metadata. |
| `StrategyTranslator.status` | Reports the selected provider, model, key availability, and output format. |
| `Translation` | Bundles the validated strategy, provider, server-generated compatibility YAML, normalized description, clarifications, and confirmation flag. |
| `ambiguity_notes` | Detects missing volume multipliers, missing loss percentages, and subjective timing or trend language. |
| `validated_model_strategy` | Parses one JSON object, rejects unsupported schema content, and performs only the disclosed reverse-crossover repair. |

## Assistance and confirmation

The model must not invent missing thresholds, windows, multipliers, or risk percentages. For instructions such as “high volume” or “exit on loss threshold,” the API returns explicit clarification notes and the browser asks the user to approve or revise the concrete proposal before execution. The confirmation preview is also shown for fully specified generated strategies as a safety boundary.

The LLM never writes Python, YAML, expressions, or repository files. It can only propose one declarative JSON object. Google AI Studio requests `application/json`; OpenAI and Anthropic receive the same JSON-only system contract. The backend validates that object and generates legacy YAML itself only to preserve existing `/api/backtest` compatibility.

If the model returns an empty exit rule for a crossover strategy, `validated_model_strategy` can propose only the inverse crossover as a constrained repair. That repair is disclosed in the confirmation warnings. Other invalid model output is rejected rather than guessed.

## Configuration

Copy `conf/app.example.yaml` to ignored `conf/app.yaml`, then select `google`, `openai`, or `anthropic` under `llm.provider`. Use `.env` only for provider credentials: `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`. Google ships in the base installation; install an optional adapter with `pip install -e '.[llm-openai]'` or `pip install -e '.[llm-anthropic]'` before selecting it.

The default timeout is 45 seconds. Process environment variables and `.env` override `conf/app.yaml`; `GBB_CONFIG_PATH` selects a different configuration file. Without a key, or when a provider returns a timeout, quota, model, or availability error, the local translator supports explicit SMA/EMA, MACD, RSI, Bollinger, Donchian, Darvas, Fibonacci, and single-stock relative-strength rules. It also preserves explicit volume filters and fixed, profit, trailing, ATR, and time-based risk controls. It rejects missing values rather than filling them silently, and the API error explains what the user must clarify.

Every provider-generated or locally translated strategy still enters the same confirmation dialog. Risk settings such as an 8% trailing stop are displayed with the normalized description before research runs.

The API key remains server-side and is never returned to the browser or stored in DuckDB.
