from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    configured = os.getenv(name, "").strip()
    if not configured:
        return default
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    frontend_directory: Path = _path_from_env("GBB_FRONTEND_DIRECTORY", PROJECT_ROOT / "app")
    database_path: Path = _path_from_env("GBB_DATABASE_PATH", PROJECT_ROOT / "data" / "gbb_terminal.duckdb")
    log_directory: Path = _path_from_env("GBB_LOG_DIRECTORY", PROJECT_ROOT / "log")
    refresh_interval_seconds: int = int(os.getenv("GBB_REFRESH_INTERVAL_SECONDS", "900"))

    @property
    def frontend_static_directory(self) -> Path:
        return self.frontend_directory / "static"

    @property
    def frontend_index(self) -> Path:
        return self.frontend_directory / "index.html"


settings = Settings()
