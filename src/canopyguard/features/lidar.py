"""Select airborne LiDAR surveys available before a target survey."""

from __future__ import annotations

from datetime import date
from typing import Any


def _survey(config: dict[str, Any], epoch: str) -> dict[str, Any]:
    survey = next(
        (item for item in config.get("epochs", []) if item.get("name") == epoch),
        None,
    )
    if survey is None:
        raise ValueError(f"Unknown LiDAR epoch: {epoch}")
    return survey


def _survey_date(survey: dict[str, Any], field: str) -> date:
    try:
        return date.fromisoformat(survey[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"LiDAR epoch {survey['name']} needs a valid {field} date"
        ) from error


def select_lidar_feature_epoch(
    config: dict[str, Any],
    epoch: str,
    *,
    target_epoch: str,
    prediction_cutoff: str,
) -> dict[str, Any]:
    """Admit a completed feature survey before the target survey begins."""
    try:
        cutoff = date.fromisoformat(prediction_cutoff)
    except ValueError as error:
        raise ValueError("prediction_cutoff must use YYYY-MM-DD") from error

    target = _survey(config, target_epoch)
    if cutoff >= _survey_date(target, "start"):
        raise ValueError("prediction cutoff must precede target LiDAR survey")
    if epoch == target_epoch:
        raise ValueError("target LiDAR survey cannot be a feature")

    survey = _survey(config, epoch)
    survey_end = _survey_date(survey, "end")
    if survey_end > cutoff:
        raise ValueError(f"LiDAR epoch {epoch} ends after prediction cutoff")
    return survey
