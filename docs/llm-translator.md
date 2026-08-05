# LLM Strategy Translator

Source: `src/gbb_terminal/llm/translator.py`

## Business definition

The translator turns a trader's natural-language intent into GBB Strategy YAML. It is a translation layer only; the strategy factory remains the authority that accepts or rejects the output.

## Functions

| Name | Definition |
| --- | --- |
| `StrategyTranslator.translate` | Sends the instruction and constrained schema to the selected provider, validates the returned YAML, and supplies confirmation metadata. |
| `StrategyTranslator.status` | Reports the selected provider, model, key availability, and output format. |
| `Translation` | Bundles the validated strategy, provider, normalized YAML and description, clarifications, and confirmation flag. |
| `ambiguity_notes` | Detects missing volume multipliers, missing loss percentages, and subjective timing or trend language. |

## Assistance and confirmation

The model must not invent missing thresholds, windows, multipliers, or risk percentages. For instructions such as “high volume” or “exit on loss threshold,” the API returns explicit clarification notes and the browser asks the user to approve or revise the concrete proposal before execution. The confirmation preview is also shown for fully specified generated strategies as a safety boundary.

The LLM never writes Python or repository files. It can only propose the declarative YAML vocabulary accepted by `StrategyFactory`.

If the model returns an empty exit rule for a crossover strategy, `validated_model_strategy` can propose only the inverse crossover as a constrained repair. That repair is disclosed in the confirmation warnings. Other invalid model output is rejected rather than guessed.

## Configuration

Copy `conf/app.example.yaml` to ignored `conf/app.yaml`, then select `google`, `openai`, or `anthropic` under `llm.provider`. Use `.env` only for provider credentials: `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`. Google ships in the base installation; install an optional adapter with `pip install -e '.[llm-openai]'` or `pip install -e '.[llm-anthropic]'` before selecting it.

The default timeout is 45 seconds. Process environment variables and `.env` override `conf/app.yaml`; `GBB_CONFIG_PATH` selects a different configuration file. Without a key, or when a provider returns a timeout/quota/provider error, the translator can propose a deterministic moving-average crossover when two MA windows are present. The confirmation warning states that non-MA clauses were omitted; instructions without a deterministic fallback return an API error instead of being guessed.

The API key remains server-side and is never returned to the browser or stored in DuckDB.
