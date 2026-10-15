"""Run the issue 8 spatial growth-curve gate from screened local cells."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from canopyguard.data.fire_perimeters import file_hash
from canopyguard.evaluation.growth_outputs import (
    _fit_parameters,
    _per_type,
    _save_oof,
    _save_preflight,
)
from canopyguard.evaluation.growth_screen import (
    fold_saturation_shares,
    saturation_shares,
    selection_masks,
    wire_exclusion,
)
from canopyguard.forecasting.growth_curve import (
    block_mae_interval,
    blocked_predictions,
)
from canopyguard.forecasting.growth_report import write_growth_report
from canopyguard.io import ensure_parent, project_root


def _load_inputs(forecast: dict, settings: dict) -> tuple[pd.DataFrame, dict]:
    root = project_root()
    with np.load(root / forecast["labels_path"], allow_pickle=False) as source:
        labels = {name: source[name] for name in source.files}
    table = pd.read_parquet(root / forecast["clean_screen"]["output_path"])
    if not np.array_equal(table["cell_id"].to_numpy(), labels["cell_id"]):
        raise ValueError("Clean screen and label archive have different cell order")
    flags_path = root / forecast["clean_screen"]["wire_flags_path"]
    if not flags_path.exists():
        raise FileNotFoundError(f"PR 13 wire flags are required: {flags_path}")
    with np.load(flags_path, allow_pickle=False) as source:
        archive = {name: source[name] for name in source.files}
    eligible = ~table["overlap_disputed"].to_numpy() & np.isfinite(
        labels["mean_change"]
    )
    joined = wire_exclusion(
        labels["cell_id"][eligible], archive, settings["p95_wire_exclusion_m"]
    )
    columns = {
        "wire_suspect": "p95_wire_suspect",
        "within_line": "p95_within_line",
        "excluded": "p95_wire_excluded",
    }
    for name, values in joined.items():
        column = np.zeros(len(table), dtype=bool)
        column[eligible] = values
        table[columns[name]] = column
    table["label_change_valid"] = np.isfinite(labels["mean_change"])
    heights = {
        name: labels[name]
        for name in ("p95_start", "p95_end", "mean_start", "mean_end")
    }
    return table, heights


def _selected(table: pd.DataFrame, heights: dict, mask: np.ndarray) -> tuple:
    frame = table.loc[mask].reset_index(drop=True)
    values = {name: data[mask] for name, data in heights.items()}
    if any(not np.isfinite(array).all() for array in values.values()):
        raise ValueError("Selected cells contain missing canopy heights")
    return frame, values


def _score(
    frame: pd.DataFrame,
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    block_size: int,
    settings: dict,
    *,
    a_mode: str,
) -> tuple[dict, dict]:
    predicted = blocked_predictions(
        frame, start, end, dt, block_size, settings, a_mode=a_mode
    )
    curve_error = predicted["curve"] - end
    median_error = predicted["median"] - end
    zero_error = start - end
    interval_settings = {
        "draws": settings["bootstrap_draws"],
        "seed": settings["seed"],
    }
    score = {
        "cells": len(frame),
        "blocks": int(np.unique(predicted["blocks"]).size),
        "folds": settings["folds"],
        "mae_no_change_m": float(np.mean(np.abs(zero_error))),
        "mae_median_growth_m": float(np.mean(np.abs(median_error))),
        "mae_curve_m": float(np.mean(np.abs(curve_error))),
        "literature_fallback_cells": int(predicted["literature_fallback"].sum()),
        "literature_fallback_classes": sorted(
            frame.loc[predicted["literature_fallback"], "vegetation_type"].unique()
        ),
        "curve_minus_no_change": block_mae_interval(
            curve_error, zero_error, predicted["blocks"], **interval_settings
        ),
        "curve_minus_median_growth": block_mae_interval(
            curve_error, median_error, predicted["blocks"], **interval_settings
        ),
    }
    return score, predicted


def _check_fit_permission(settings: dict, shares: dict) -> None:
    missing = [name for name, item in shares.items() if item["A_m"] is None]
    if missing:
        raise ValueError(f"Unconfirmed literature A: {', '.join(missing)}")
    if not settings["source_review_confirmed"] or not settings["reviewer_spot_checked"]:
        raise ValueError(
            "Height table needs Lakshay confirmation and reviewer spot-check"
        )


def growth_preflight(forecast: dict) -> tuple:
    """Write selection and A-saturation checks without fitting any curve."""
    settings = forecast["growth_curve"]
    table, heights = _load_inputs(forecast, settings)
    masks = selection_masks(table, settings)
    forest_frame, forest_heights = _selected(table, heights, masks["forest_loss_on"])
    shares = saturation_shares(
        forest_frame, forest_heights["p95_start"], settings["max_height_m"]
    )
    _save_preflight(forecast, settings, shares, masks, table)
    return table, heights, masks, forest_frame, forest_heights, shares


def run_growth_gate(forecast: dict) -> dict:
    """Compare forest growth curves after explicit source and wire preflight."""
    root = project_root()
    settings = forecast["growth_curve"]
    table, heights, masks, forest_frame, forest_heights, shares = growth_preflight(
        forecast
    )
    _check_fit_permission(settings, shares)
    dt = float(
        json.loads((root / settings["time_gap_source"]).read_text(encoding="utf-8"))[
            "baseline_years"
        ]
    )
    screens = {}
    primary_predictions = None
    for screen_name in (
        "forest_loss_on",
        "forest_loss_off",
        "all_loss_on",
        "all_loss_off",
    ):
        frame, values = _selected(table, heights, masks[screen_name])
        mode = (
            settings["primary_a_mode"] if screen_name.startswith("forest") else "free"
        )
        score, predicted = _score(
            frame,
            values["p95_start"],
            values["p95_end"],
            dt,
            settings["primary_block_m"],
            settings,
            a_mode=mode,
        )
        screens[screen_name] = {"model": mode, **score}
        if screen_name == "forest_loss_on":
            primary_predictions = predicted
    primary = screens["forest_loss_on"]
    sensitivities = {}
    for mode in ("literature", "free", "record"):
        sensitivities[mode], _ = _score(
            forest_frame,
            forest_heights["p95_start"],
            forest_heights["p95_end"],
            dt,
            settings["primary_block_m"],
            settings,
            a_mode=mode,
        )
    spatial = {}
    for size in settings["block_sizes_m"]:
        if size == settings["primary_block_m"]:
            continue
        spatial[str(size)], _ = _score(
            forest_frame,
            forest_heights["p95_start"],
            forest_heights["p95_end"],
            dt,
            size,
            settings,
            a_mode=settings["primary_a_mode"],
        )
    mean_score, _ = _score(
        forest_frame,
        forest_heights["mean_start"],
        forest_heights["mean_end"],
        dt,
        settings["primary_block_m"],
        settings,
        a_mode="literature",
    )
    fitted = _fit_parameters(
        forest_frame,
        forest_heights["p95_start"],
        forest_heights["p95_end"],
        dt,
        settings,
    )
    fold_shares = fold_saturation_shares(
        forest_frame, forest_heights["p95_start"], primary_predictions["A"]
    )
    per_type = _per_type(
        forest_frame,
        forest_heights["p95_start"],
        forest_heights["p95_end"],
        primary_predictions,
        fitted,
        fold_shares,
        settings,
    )
    decision = "PASS" if primary["curve_minus_no_change"]["ci_high_m"] < 0 else "FAIL"
    _save_oof(
        forest_frame,
        forest_heights["p95_start"],
        forest_heights["p95_end"],
        primary_predictions,
        settings,
        forecast,
    )
    metrics = {
        "issue": 8,
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_base_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "baseline_years": dt,
        "decision": decision,
        "settings": settings,
        "input_sha256": {
            "labels": file_hash(root / forecast["labels_path"]),
            "clean_cells": file_hash(root / forecast["clean_screen"]["output_path"]),
            "wire_flags": file_hash(root / forecast["clean_screen"]["wire_flags_path"]),
            "vegetation": file_hash(root / forecast["vegetation_join"]["output_path"]),
        },
        "screens": screens,
        "height_sensitivities": sensitivities,
        "spatial_sensitivities": spatial,
        "mean_secondary": mean_score,
        "forest_saturation": fold_shares,
        "literature_saturation": shares,
        "per_type": per_type,
    }
    path = ensure_parent(root / settings["metrics_path"])
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_growth_report(metrics, forecast)
    return metrics
