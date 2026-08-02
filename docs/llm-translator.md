# LLM Strategy Translator

Source: `app/llm.py`

## Business definition

The translator turns a trader's natural-language intent into GBB Strategy YAML. It is a translation layer only; the strategy factory remains the authority that accepts or rejects the output.

## Functions

| Name | Definition |
| --- | --- |
| `GoogleAIStrategyTranslator.translate` | Sends the instruction and constrained schema to Google AI Studio, then validates the returned YAML. |
| `GoogleAIStrategyTranslator.status` | Reports provider, model, key availability, and output format. |
| `Translation` | Bundles the validated `Strategy`, provider name, and normalized YAML. |

## Configuration

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the ignored `.env` file. Without a key, the translator supports deterministic moving-average crossover instructions.

The API key remains server-side and is never returned to the browser or stored in DuckDB.
