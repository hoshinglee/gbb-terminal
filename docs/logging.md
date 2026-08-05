# Application Logging

Source: `src/gbb_terminal/observability/logging.py`

## Business definition

Persistent logs provide a local operational trail for data refresh failures, strategy proposals, rejected requests, duplicate migrations, and completed backtests without placing secrets or full market datasets in Git.

## Functions

| Name | Definition |
| --- | --- |
| `configure_logging` | Creates the project logger once with console and rotating-file handlers. |
| `get_logger` | Returns a named child logger for a module. |
| `log_event` | Writes a searchable event name and JSON-serialized business fields. |

## Storage and rotation

Logs are written to `log/gbb_terminal.log`. A file rotates at 5 MB and retains five backups. The entire project `log/` directory is excluded from Git.

Request logs include a generated request ID, HTTP method, path, response status, and duration. Strategy events contain semantic keys and counts but never the Google AI Studio API key or full `.env` content.
