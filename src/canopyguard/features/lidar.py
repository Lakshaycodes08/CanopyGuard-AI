"""Select airborne LiDAR surveys available at a prediction cutoff."""

from __future__ import annotations

from datetime import date
from typing import Any


def select_lidar_feature_epoch(
    config: dict[str, Any], epoch: str, prediction_cutoff: str
) -> dict[str, Any]:
    """Return a survey only if its full acquisition ended by the cutoff."""
    try:
        cutoff = date.fromisoformat(prediction_cutoff)
    except ValueError as error:
        raise ValueError("prediction_cutoff must use YYYY-MM-DD") from error

    survey = next(
        (item for item in config.get("epochs", []) if item.get("name") == epoch),
        None,
    )
    if survey is None:
        raise ValueError(f"Unknown LiDAR epoch: {epoch}")

    try:
        survey_end = date.fromisoformat(survey["end"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"LiDAR epoch {epoch} needs a valid end date") from error

    if survey_end > cutoff:
        raise ValueError(f"LiDAR epoch {epoch} ends after prediction cutoff")
    return survey
