"""Paired block-bootstrap contrasts between held-out predictions."""

from __future__ import annotations

from typing import Any

import pandas as pd

from canopyguard.evaluation.bootstrap import excludes_zero, paired_block_bootstrap
from canopyguard.forecasting.growth_model import paired_error_vectors


def bootstrap_pairs(
    held_out: pd.DataFrame, settings: dict[str, Any], seed: int
) -> dict[str, dict[str, float]]:
    """MAE difference (first minus second) per configured model pair."""
    predictions = {
        column.removeprefix("pred_"): held_out[column].to_numpy()
        for column in held_out.columns
        if column.startswith("pred_")
    }
    y = held_out["y"].to_numpy()
    results = {}
    for first, second in settings["pairs"]:
        errors_a, errors_b = paired_error_vectors(y, predictions, first, second)
        result = paired_block_bootstrap(
            errors_a,
            errors_b,
            held_out["block_id"],
            resamples=int(settings["resamples"]),
            confidence_level=float(settings["confidence_level"]),
            seed=seed,
        )
        result["excludes_zero"] = bool(excludes_zero(result))
        results[f"{first}_minus_{second}"] = result
    return results
