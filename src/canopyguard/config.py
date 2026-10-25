from __future__ import annotations

from datetime import date
from itertools import pairwise
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
        data = yaml.safe_load(file)

    if data is None:
        return {}

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


def validate_time_splits(config: dict[str, Any]) -> None:
    """Validate chronological train, validation, and test boundaries."""
    require_keys(config, ["dates", "splits"])
    dates = config["dates"]
    splits = config["splits"]
    if not isinstance(dates, dict) or not isinstance(splits, dict):
        raise ValueError("Dates and splits must be YAML mappings")

    require_keys(dates, ["start", "end"])
    split_keys = [
        "train_end",
        "validation_start",
        "validation_end",
        "test_start",
        "test_end",
    ]
    require_keys(splits, split_keys)

    try:
        study_start = date.fromisoformat(str(dates["start"]))
        study_end = date.fromisoformat(str(dates["end"]))
        boundaries = [date.fromisoformat(str(splits[key])) for key in split_keys]
    except ValueError as error:
        raise ValueError(
            "Study dates and split boundaries must use YYYY-MM-DD"
        ) from error

    ordered = [study_start, *boundaries]
    if any(left >= right for left, right in pairwise(ordered)):
        raise ValueError(
            "Time splits must be strictly chronological and non-overlapping"
        )
    if boundaries[-1] > study_end:
        raise ValueError("Test split must end within the study dates")


def load_region(name: str) -> dict[str, Any]:
    """Bounding box, label pair and output-name suffix for a named region.

    The original study area is region `study` and keeps its existing paths.
    """
    primary = load_config("configs/lidar.yaml")["change"]["pairs"][0]
    if name == "study":
        box = load_config("configs/study_area.yaml")["study_area"]["bbox"]
        suffix, pair, reserved = "", list(primary), False
    else:
        regions = load_config("configs/regions.yaml")["regions"]
        if name not in regions:
            msg = f"Unknown region {name!r}; choose from {sorted(regions)}"
            raise KeyError(msg)
        entry = regions[name]
        box, suffix = entry["bbox"], f"_{name}"
        pair = list(entry.get("pair", primary))
        reserved = bool(entry.get("reserved", False))
    return {
        "name": name,
        "suffix": suffix,
        "pair": pair,
        "primary_end": str(primary[1]),
        "reserved": reserved,
        "bbox": tuple(float(box[k]) for k in ("west", "south", "east", "north")),
    }
