"""Store issue 8 preflight, fitted parameters and held-out predictions."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from canopyguard.forecasting.growth_curve import (
    block_mae_interval,
    class_heights,
    fit_growth_curve,
)
from canopyguard.forecasting.growth_prior import training_scope
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import current_commit, file_sha256, write_provenance


def _fit_parameters(frame: pd.DataFrame, start, end, dt, settings) -> dict:
    groups = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    names = frame["vegetation_type"].to_numpy()
    mode = settings["primary_a_mode"]
    all_heights = class_heights(names, start, end, settings, mode)
    fitted, output = {}, {}
    for name in np.unique(names):
        use = names == name
        model_group = groups[np.flatnonzero(use)[0]]
        broad_group = broad[np.flatnonzero(use)[0]]
        scope, training = training_scope(
            model_group,
            broad_group,
            np.ones(len(frame), dtype=bool),
            groups,
            broad,
            settings["min_fit_cells"],
        )
        if scope not in fitted:
            ceilings = class_heights(
                names[training], start[training], end[training], settings, mode
            )
            ceiling = np.array([ceilings[item] for item in names[training]])
            fitted[scope] = fit_growth_curve(
                start[training], end[training], dt, settings, max_height_m=ceiling
            )
        output[name] = {
            "scope": scope,
            **fitted[scope],
            "A": all_heights[name],
        }
    return output


def _per_type(frame, start, end, predicted, fitted, shares, settings) -> list[dict]:
    rows = []
    names = frame["vegetation_type"].to_numpy()
    for name in np.unique(names):
        use = names == name
        curve_error = predicted["curve"][use] - end[use]
        median_error = predicted["median"][use] - end[use]
        zero_error = start[use] - end[use]
        blocks = predicted["blocks"][use]
        interval = None
        if np.unique(blocks).size >= 2:
            interval = block_mae_interval(
                curve_error,
                zero_error,
                blocks,
                draws=settings["bootstrap_draws"],
                seed=settings["seed"],
            )
        rows.append(
            {
                "vegetation_type": name,
                "broader_group": frame.loc[use, "broader_group"].iloc[0],
                "cells": int(use.sum()),
                "fit": fitted[name],
                "saturation": shares[name],
                "mae_no_change_m": float(np.mean(np.abs(zero_error))),
                "mae_median_growth_m": float(np.mean(np.abs(median_error))),
                "mae_curve_m": float(np.mean(np.abs(curve_error))),
                "curve_minus_no_change": interval,
            }
        )
    return sorted(rows, key=lambda row: -row["cells"])


def _save_preflight(
    forecast: dict, settings: dict, shares: dict, masks: dict, table
) -> None:
    root = project_root()
    path = ensure_parent(root / settings["preflight_path"])
    record = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "git_revision": current_commit(root),
        "inputs_sha256": {
            "labels": file_sha256(root / forecast["labels_path"]),
            "clean_cells": file_sha256(root / forecast["clean_screen"]["output_path"]),
            "wire_flags": file_sha256(
                root / forecast["clean_screen"]["wire_flags_path"]
            ),
        },
        "source_review_confirmed": settings["source_review_confirmed"],
        "reviewer_spot_checked": settings["reviewer_spot_checked"],
        "screen_counts": {name: int(mask.sum()) for name, mask in masks.items()},
        "wire_suspect_cells": int(table["p95_wire_suspect"].sum()),
        "within_10m_line_cells": int(table["p95_within_line"].sum()),
        "forest_saturation": shares,
    }
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _save_oof(frame, start, end, predicted, settings, forecast) -> None:
    root = project_root()
    table = pd.DataFrame(
        {
            "cell_id": frame["cell_id"],
            "block_id": predicted["blocks"],
            "fold": predicted["folds"],
            "p95_start": start,
            "p95_end": end,
            "p95_no_change": start,
            "p95_median_growth": predicted["median"],
            "p95_curve": predicted["curve"],
            "p95_fold_A": predicted["A"],
        }
    )
    path = ensure_parent(root / settings["oof_path"])
    table.to_parquet(path, index=False)
    screen = json.loads(
        (root / forecast["clean_screen"]["output_path"])
        .with_suffix(".provenance.json")
        .read_text(encoding="utf-8")
    )
    write_provenance(
        path,
        source_url="https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8",
        script_name="run_growth_curve_check.py",
        bbox_wgs84=tuple(float(value) for value in screen["study_bbox"]),
        crs="EPSG:6339",
        row_count=len(table),
    )
