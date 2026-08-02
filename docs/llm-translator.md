# LLM Strategy Translator

Source: `app/llm.py`

## Business definition

The translator turns a trader's natural-language intent into GBB Strategy YAML. It is a translation layer only; the strategy factory remains the authority that accepts or rejects the output.

## Functions

| Name | Definition |
| --- | --- |
| `GoogleAIStrategyTranslator.translate` | Sends the instruction and constrained schema to Google AI Studio, validates the returned YAML, and supplies confirmation metadata. |
| `GoogleAIStrategyTranslator.status` | Reports provider, model, key availability, and output format. |
| `Translation` | Bundles the validated strategy, provider, normalized YAML and description, clarifications, and confirmation flag. |
| `ambiguity_notes` | Detects missing volume multipliers, missing loss percentages, and subjective timing or trend language. |

## Assistance and confirmation

The model must not invent missing thresholds, windows, multipliers, or risk percentages. For instructions such as “high volume” or “exit on loss threshold,” the API returns explicit clarification notes and the browser asks the user to approve or revise the concrete proposal before execution. The confirmation preview is also shown for fully specified generated strategies as a safety boundary.

The LLM never writes Python or repository files. It can only propose the declarative YAML vocabulary accepted by `StrategyFactory`.

If the model returns an empty exit rule for a crossover strategy, `validated_model_strategy` can propose only the inverse crossover as a constrained repair. That repair is disclosed in the confirmation warnings. Other invalid model output is rejected rather than guessed.

## Configuration

Set `GEMINI_API_KEY`, `GEMINI_MODEL`, and optional `GEMINI_TIMEOUT_MS` in the ignored `.env` file. The default provider timeout is 45 seconds. Without a key, or when Google returns a timeout/quota/provider error, the translator can propose a deterministic moving-average crossover when two MA windows are present. The confirmation warning states that non-MA clauses were omitted; instructions without a deterministic fallback return an API error instead of being guessed.

The API key remains server-side and is never returned to the browser or stored in DuckDB.
