"""Select LiDAR surveys and ECHOSAT years available before a target survey."""

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


def _cutoff_before_target(
    config: dict[str, Any], target_epoch: str, prediction_cutoff: str
) -> date:
    try:
        cutoff = date.fromisoformat(prediction_cutoff)
    except ValueError as error:
        raise ValueError("prediction_cutoff must use YYYY-MM-DD") from error

    target = _survey(config, target_epoch)
    if cutoff >= _survey_date(target, "start"):
        raise ValueError("prediction cutoff must precede target LiDAR survey")
    return cutoff


def select_lidar_feature_epoch(
    config: dict[str, Any],
    epoch: str,
    *,
    target_epoch: str,
    prediction_cutoff: str,
) -> dict[str, Any]:
    """Admit a completed feature survey before the target survey begins."""
    cutoff = _cutoff_before_target(config, target_epoch, prediction_cutoff)
    if epoch == target_epoch:
        raise ValueError("target LiDAR survey cannot be a feature")

    survey = _survey(config, epoch)
    survey_end = _survey_date(survey, "end")
    if survey_end > cutoff:
        raise ValueError(f"LiDAR epoch {epoch} ends after prediction cutoff")
    return survey


def select_echosat_feature_years(
    band_years: list[int],
    lidar_config: dict[str, Any],
    *,
    target_epoch: str,
    prediction_cutoff: str,
) -> list[int]:
    """Admit ECHOSAT years that end on or before the cutoff.

    A band covers its whole calendar year, so year Y is admitted only when
    31 December of Y is not after the cutoff. The cutoff must also precede the
    target survey, so no band dated after the cutoff becomes a feature.
    """
    cutoff = _cutoff_before_target(lidar_config, target_epoch, prediction_cutoff)
    return [year for year in band_years if date(year, 12, 31) <= cutoff]
