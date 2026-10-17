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
    last_input_year: int,
    allowed_as_feature: bool,
) -> list[int]:
    """Admit ECHOSAT years only when allowed and all input imagery predates the cutoff.

    `allowed_as_feature` is the config switch; it is off while ECHOSAT is a
    benchmark only.

    ECHOSAT predicts every year in one pass from the imagery of all years, so
    even the 2018 band depends on imagery through `last_input_year`. A band is
    therefore a safe feature only when 31 December of that last input year is
    not after the cutoff. The cutoff must also precede the target survey, so for
    any real forecast this returns no years and ECHOSAT is a benchmark only.
    """
    cutoff = _cutoff_before_target(lidar_config, target_epoch, prediction_cutoff)
    if not allowed_as_feature or date(last_input_year, 12, 31) > cutoff:
        return []
    return list(band_years)
