"""Run the issue 8 spatial growth-curve gate from screened local cells."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from canopyguard.data.fire_perimeters import file_hash
from canopyguard.forecasting.growth_curve import (
    block_mae_interval,
    blocked_predictions,
    fit_growth_curve,
)
from canopyguard.forecasting.growth_report import write_growth_report
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import write_provenance


def _load_cells(forecast: dict) -> tuple[pd.DataFrame, dict]:
    root = project_root()
    with np.load(root / forecast["labels_path"], allow_pickle=False) as source:
        labels = {name: source[name] for name in source.files}
    table = pd.read_parquet(root / forecast["clean_screen"]["output_path"])
    if not np.array_equal(table["cell_id"].to_numpy(), labels["cell_id"]):
        raise ValueError("Clean screen and label archive have different cell order")
    chosen = table["clean"].to_numpy()
    frame = table.loc[chosen].reset_index(drop=True)
    heights = {
        key: labels[key][chosen]
        for key in ("p95_start", "p95_end", "mean_start", "mean_end")
    }
    if any(not np.isfinite(values).all() for values in heights.values()):
        raise ValueError("Clean cells contain missing canopy heights")
    return frame, heights


def _scores(
    frame: pd.DataFrame,
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    block_size: int,
    settings: dict,
) -> tuple[dict, dict]:
    predictions = blocked_predictions(frame, start, end, dt, block_size, settings)
    curve_error = predictions["curve"] - end
    median_error = predictions["median"] - end
    no_change_error = start - end
    interval = block_mae_interval(
        curve_error,
        no_change_error,
        predictions["blocks"],
        draws=settings["bootstrap_draws"],
        seed=settings["seed"],
    )
    median_interval = block_mae_interval(
        curve_error,
        median_error,
        predictions["blocks"],
        draws=settings["bootstrap_draws"],
        seed=settings["seed"],
    )
    score = {
        "cells": len(frame),
        "blocks": int(np.unique(predictions["blocks"]).size),
        "folds": settings["folds"],
        "mae_no_change_m": float(np.mean(np.abs(no_change_error))),
        "mae_median_growth_m": float(np.mean(np.abs(median_error))),
        "mae_curve_m": float(np.mean(np.abs(curve_error))),
        "curve_minus_no_change": interval,
        "curve_minus_median_growth": median_interval,
    }
    return score, predictions


def _final_parameters(
    frame: pd.DataFrame, start: np.ndarray, end: np.ndarray, dt: float, settings: dict
) -> dict:
    groups = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    names = frame["vegetation_type"].to_numpy()
    fitted = {}
    output = {}
    for name in np.unique(names):
        use = names == name
        model_group = groups[np.flatnonzero(use)[0]]
        broad_group = broad[np.flatnonzero(use)[0]]
        own = groups == model_group
        if (
            not model_group.startswith("group:")
            and own.sum() >= settings["min_fit_cells"]
        ):
            scope, training = "type:" + model_group, own
        else:
            scope, training = "broad:" + broad_group, broad == broad_group
        if scope not in fitted:
            fitted[scope] = fit_growth_curve(
                start[training],
                end[training],
                dt,
                settings,
                maximum_start_height=float(np.max(start[training])),
            )
        output[name] = {"scope": scope, **fitted[scope]}
    return output


def _per_type(
    frame: pd.DataFrame,
    start: np.ndarray,
    end: np.ndarray,
    predictions: dict,
    parameters: dict,
    settings: dict,
) -> list[dict]:
    rows = []
    names = frame["vegetation_type"].to_numpy()
    for name in np.unique(names):
        use = names == name
        curve_error = predictions["curve"][use] - end[use]
        zero_error = start[use] - end[use]
        block_ids = predictions["blocks"][use]
        interval = None
        if np.unique(block_ids).size >= 2:
            interval = block_mae_interval(
                curve_error,
                zero_error,
                block_ids,
                draws=settings["bootstrap_draws"],
                seed=settings["seed"],
            )
        rows.append(
            {
                "vegetation_type": name,
                "broader_group": frame.loc[use, "broader_group"].iloc[0],
                "cells": int(use.sum()),
                "fit": parameters[name],
                "mae_no_change_m": float(np.mean(np.abs(zero_error))),
                "mae_median_growth_m": float(
                    np.mean(np.abs(predictions["median"][use] - end[use]))
                ),
                "mae_curve_m": float(np.mean(np.abs(curve_error))),
                "curve_minus_no_change": interval,
            }
        )
    return sorted(rows, key=lambda row: -row["cells"])


def _forest_only_score(
    frame: pd.DataFrame,
    start: np.ndarray,
    end: np.ndarray,
    predictions: dict,
    settings: dict,
) -> dict:
    forest = frame["broader_group"].isin(settings["forest_groups"]).to_numpy()
    blocks = predictions["blocks"][forest]
    curve_error = predictions["curve"][forest] - end[forest]
    median_error = predictions["median"][forest] - end[forest]
    zero_error = start[forest] - end[forest]
    return {
        "cells": int(forest.sum()),
        "blocks": int(np.unique(blocks).size),
        "mae_no_change_m": float(np.mean(np.abs(zero_error))),
        "mae_median_growth_m": float(np.mean(np.abs(median_error))),
        "mae_curve_m": float(np.mean(np.abs(curve_error))),
        "curve_minus_no_change": block_mae_interval(
            curve_error,
            zero_error,
            blocks,
            draws=settings["bootstrap_draws"],
            seed=settings["seed"],
        ),
        "curve_minus_median_growth": block_mae_interval(
            curve_error,
            median_error,
            blocks,
            draws=settings["bootstrap_draws"],
            seed=settings["seed"],
        ),
    }


def run_growth_gate(forecast: dict) -> dict:
    """Fit, compare, bootstrap and render the tracked G3 report."""
    root = project_root()
    settings = forecast["growth_curve"]
    frame, heights = _load_cells(forecast)
    dt = float(
        json.loads((root / settings["time_gap_source"]).read_text(encoding="utf-8"))[
            "baseline_years"
        ]
    )
    results = {}
    primary_predictions = None
    for block_size in settings["block_sizes_m"]:
        size_results = {}
        for target in ("p95", "mean"):
            start, end = heights[f"{target}_start"], heights[f"{target}_end"]
            score, predictions = _scores(
                frame, start, end, dt, int(block_size), settings
            )
            size_results[target] = score
            print(
                f"{block_size} m {target}: curve {score['mae_curve_m']:.3f}, "
                f"no change {score['mae_no_change_m']:.3f}",
                flush=True,
            )
            if int(block_size) == settings["primary_block_m"] and target == "p95":
                primary_predictions = predictions
        results[str(block_size)] = size_results
    if primary_predictions is None:
        raise ValueError("Primary block size is absent from sensitivity sizes")
    p95_start, p95_end = heights["p95_start"], heights["p95_end"]
    parameters = _final_parameters(frame, p95_start, p95_end, dt, settings)
    per_type = _per_type(
        frame, p95_start, p95_end, primary_predictions, parameters, settings
    )
    primary = results[str(settings["primary_block_m"])]["p95"]
    decision = "PASS" if primary["curve_minus_no_change"]["ci_high_m"] < 0 else "FAIL"
    oof = pd.DataFrame(
        {
            "cell_id": frame["cell_id"],
            "block_id": primary_predictions["blocks"],
            "fold": primary_predictions["folds"],
            "p95_start": p95_start,
            "p95_end": p95_end,
            "p95_no_change": p95_start,
            "p95_median_growth": primary_predictions["median"],
            "p95_curve": primary_predictions["curve"],
        }
    )
    oof_path = ensure_parent(root / settings["oof_path"])
    oof.to_parquet(oof_path, index=False)
    screen_record = json.loads(
        (root / forecast["clean_screen"]["output_path"])
        .with_suffix(".provenance.json")
        .read_text(encoding="utf-8")
    )
    bbox = screen_record["study_bbox"]
    write_provenance(
        oof_path,
        source_url="https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8",
        script_name="run_growth_curve_check.py",
        bbox_wgs84=tuple(float(value) for value in bbox),
        crs="EPSG:6339",
        row_count=len(oof),
    )
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    metrics = {
        "issue": 8,
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_base_revision": revision,
        "baseline_years": dt,
        "decision": decision,
        "screened_cells": len(frame),
        "settings": settings,
        "input_sha256": {
            "labels": file_hash(root / forecast["labels_path"]),
            "clean_cells": file_hash(root / forecast["clean_screen"]["output_path"]),
            "vegetation": file_hash(root / forecast["vegetation_join"]["output_path"]),
        },
        "results": results,
        "forest_only": _forest_only_score(
            frame, p95_start, p95_end, primary_predictions, settings
        ),
        "per_type": per_type,
    }
    metrics_path = ensure_parent(root / settings["metrics_path"])
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_growth_report(metrics, forecast)
    return metrics
