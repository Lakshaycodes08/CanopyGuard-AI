from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file and return a dictionary."""
    config_path = Path(path)
    if not config_path.exists():
        msg = f"Config file not found: {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        msg = f"Config must contain a YAML mapping: {config_path}"
        raise ValueError(msg)

    return data


def require_keys(config: dict[str, Any], keys: list[str]) -> None:
    """Raise when a config is missing required top-level keys."""
    missing = [key for key in keys if key not in config]
    if missing:
        msg = "Missing required config keys: " + ", ".join(missing)
        raise ValueError(msg)
