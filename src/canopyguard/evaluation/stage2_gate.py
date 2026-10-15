"""Evaluate frozen E4/E5 residual models against the spatial stage-one prior."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import sklearn

from canopyguard.evaluation.blocks import assign_blocks, systematic_folds
from canopyguard.evaluation.growth_gate import _load_inputs
from canopyguard.evaluation.growth_screen import selection_masks
from canopyguard.forecasting.growth_curve import block_mae_interval
from canopyguard.forecasting.stage2_residual import fit_fold_models, fold_prior
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import (
    current_commit,
    file_sha256,
    read_provenance,
    study_area_box,
    write_provenance,
)

SCREEN_NAMES = ("forest_loss_off", "forest_loss_on", "all_loss_off", "all_loss_on")
MODEL_NAMES = ("ridge", "lightgbm")


def _join_inputs(forecast: dict) -> tuple[pd.DataFrame, dict, dict]:
    root = project_root()
    stage1 = forecast["stage1_growth_model"]
    settings = stage1["growth_curve"]
    table, heights = _load_inputs(stage1, settings)
    terrain_path = root / forecast["stage2_residual_model"]["terrain"]["output_path"]
    terrain = pd.read_parquet(terrain_path)
    if len(terrain) != len(table) or not np.array_equal(
        terrain["cell_id"].to_numpy(), table["cell_id"].to_numpy()
    ):
        raise ValueError("Terrain must join 1:1 in label cell_id order")
    if not table["cell_id"].is_unique:
        raise ValueError("Label cell IDs are not unique")
    for name in ("elevation_m", "slope_deg", "heat_load", "tpi_450"):
        table[name] = terrain[name].to_numpy()
    table["mean_start"] = heights["mean_start"]
    table["p95_start"] = heights["p95_start"]
    with np.load(root / stage1["labels_path"], allow_pickle=False) as labels:
        table["max_start"] = labels["max_start"]
    valid_terrain = (
        np.isfinite(table[["elevation_m", "slope_deg", "heat_load", "tpi_450"]])
        .all(axis=1)
        .to_numpy()
    )
    masks = selection_masks(table, settings)
    excluded = {
        name: int((mask & ~valid_terrain).sum()) for name, mask in masks.items()
    }
    return (
        table,
        heights,
        {"masks": masks, "valid_terrain": valid_terrain, "excluded": excluded},
    )


def _fold_predictions(frame, start, end, blocks, settings, stage1, models=MODEL_NAMES):
    folds = systematic_folds(blocks, stage1["folds"], stage1["seed"])
    output = {name: np.full(len(frame), np.nan) for name in ("stage1", *models)}
    fold_counts = []
    importance = {name: [] for name in models}
    for fold in range(stage1["folds"]):
        train, test = folds != fold, folds == fold
        increment = fold_prior(frame, start, end, train, stage1["min_fit_cells"])
        residual = end - start - increment
        output["stage1"][test] = increment[test]
        fitted, weights = fit_fold_models(
            frame, residual, train, test, settings, stage1["seed"], models
        )
        for name in models:
            output[name][test] = increment[test] + fitted[name]
            importance[name].append(weights[name])
        fold_counts.append(
            {"fold": fold, "train": int(train.sum()), "test": int(test.sum())}
        )
    if any(not np.isfinite(values).all() for values in output.values()):
        raise ValueError("Stage-two out-of-fold predictions contain nonfinite values")
    return output, fold_counts, importance, folds


def score_screen(frame, start, end, block_size, stage1, settings, models=MODEL_NAMES):
    """Fit and score a declared screen with paired whole-block intervals."""
    blocks = assign_blocks(frame["x"], frame["y"], block_size)
    predictions, fold_counts, importance, folds = _fold_predictions(
        frame, start, end, blocks, settings, stage1, models
    )
    observed = end - start
    baseline_error = predictions["stage1"] - observed
    score = {
        "cells": len(frame),
        "blocks": int(np.unique(blocks).size),
        "fold_counts": fold_counts,
        "mae_stage1_m": float(np.mean(np.abs(baseline_error))),
    }
    for name in models:
        error = predictions[name] - observed
        interval = block_mae_interval(
            error,
            baseline_error,
            blocks,
            draws=stage1["bootstrap_draws"],
            seed=stage1["seed"],
        )
        score[name] = {
            "mae_m": float(np.mean(np.abs(error))),
            "minus_stage1": interval,
            "decision": "PASS" if interval["ci_high_m"] < 0 else "FAIL",
        }
    return score, predictions, importance, folds


def _mean_importance(folds: list[dict[str, float]]) -> dict[str, float]:
    names = sorted(set().union(*(entry.keys() for entry in folds)))
    return {
        name: float(np.mean([entry.get(name, 0.0) for entry in folds]))
        for name in names
    }


def _save_primary(
    frame, start, end, predictions, folds, block_size, settings, study, hashes
):
    root = project_root()
    output = ensure_parent(root / settings["oof_path"])
    pd.DataFrame(
        {
            "cell_id": frame["cell_id"].to_numpy(),
            "fold": folds,
            "p95_start_m": start,
            "observed_change_m": end - start,
            "stage1_change_m": predictions["stage1"],
            "ridge_change_m": predictions["ridge"],
            "lightgbm_change_m": predictions["lightgbm"],
        }
    ).to_parquet(output, index=False)
    sidecar = write_provenance(
        output,
        source_url="local:2013-2022 LiDAR labels and 2012 USGS 3DEP terrain",
        script_name="run_stage2_residual_check.py",
        bbox_wgs84=study_area_box(study),
        crs=settings["terrain"]["target_crs"],
        row_count=len(frame),
    )
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    record["input_sha256"] = hashes
    record["screen"] = "forest_loss_off"
    record["block_size_m"] = block_size
    sidecar.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")


def run_stage2_gate(forecast: dict, study: dict) -> dict:
    """Run every frozen screen and block sensitivity once, then write results."""
    import lightgbm

    root = project_root()
    stage1 = forecast["stage1_growth_model"]["growth_curve"]
    settings = forecast["stage2_residual_model"]
    table, heights, selection = _join_inputs(forecast)
    paths = {
        "labels": root / forecast["stage1_growth_model"]["labels_path"],
        "clean_cells": root
        / forecast["stage1_growth_model"]["clean_screen"]["output_path"],
        "wire_flags": root
        / forecast["stage1_growth_model"]["clean_screen"]["wire_flags_path"],
        "terrain": root / settings["terrain"]["output_path"],
    }
    for path in paths.values():
        read_provenance(path)
    hashes = {name: file_sha256(path) for name, path in paths.items()}
    screens = {}
    primary_importance = None
    for size in stage1["block_sizes_m"]:
        for name in SCREEN_NAMES:
            mask = selection["masks"][name] & selection["valid_terrain"]
            frame = table.loc[mask].reset_index(drop=True)
            start = heights["p95_start"][mask]
            end = heights["p95_end"][mask]
            score, predictions, weights, folds = score_screen(
                frame, start, end, size, stage1, settings
            )
            screens[f"{name}_{size}m"] = score
            print(f"stage2 {name} {size} m: {score['cells']} cells", flush=True)
            if size == stage1["primary_block_m"] and name == "forest_loss_off":
                primary_importance = {
                    key: _mean_importance(value) for key, value in weights.items()
                }
                _save_primary(
                    frame, start, end, predictions, folds, size, settings, study, hashes
                )
    result = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_base_revision": current_commit(root),
        "preregistration": "reports/stage2_gate_prereg.md",
        "settings": settings,
        "stage1_settings": {
            key: stage1[key]
            for key in (
                "folds",
                "seed",
                "min_fit_cells",
                "bootstrap_draws",
                "block_sizes_m",
            )
        },
        "versions": {"sklearn": sklearn.__version__, "lightgbm": lightgbm.__version__},
        "input_sha256": hashes,
        "terrain_excluded": selection["excluded"],
        "screens": screens,
        "primary_feature_weights": primary_importance,
    }
    from canopyguard.forecasting.stage2_report import write_stage2_report

    ensure_parent(root / settings["metrics_path"]).write_text(
        json.dumps(result, indent=2) + "\n", "utf-8"
    )
    write_stage2_report(result)
    return result
