from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from ..settings import settings

LOG_DIRECTORY = settings.log_directory
LOG_FILE = LOG_DIRECTORY / "gbb_terminal.log"


def configure_logging() -> logging.Logger:
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gbb_terminal")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def get_logger(module_name: str) -> logging.Logger:
    return configure_logging().getChild(module_name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info("event=%s fields=%s", event, json.dumps(fields, default=str, sort_keys=True))
