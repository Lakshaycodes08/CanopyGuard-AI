"""Checks on the wire check result: placebo lines, persistence, sensitivity.

A placebo shifts the mapped lines sideways, so a real line effect should
vanish while an artifact of the method would remain. Cells near the real
lines are left out of the placebo comparison.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import shapely
from numpy.typing import NDArray

from canopyguard.lidar.wire_check import strata_keys
from canopyguard.lidar.wire_check_run import band_result, epoch_flags, line_union


def ratio_row(flags: dict, dist, tile, canopy_share, cfg: dict, exclude=None) -> dict:
    """Near-band ratios for both flag types in one epoch."""
    use = dict(flags)
    use["eligible"] = (
        flags["eligible"] & ~exclude if exclude is not None else flags["eligible"]
    )
    key = strata_keys(tile, canopy_share, use["valid"], cfg)
    result = band_result(use, "near", dist, tile, key, cfg)
    return {
        label: {k: result[label][k] for k in ("ratio", "ci_low", "ci_high")}
        for label in ("isolated", "wire_like")
    }


def persistence_counts(
    first: NDArray, second: NDArray, mask: NDArray
) -> dict[str, int]:
    """How many flagged cells are flagged in one epoch, the other, or both."""
    a, b = first & mask, second & mask
    return {
        "first": int(a.sum()),
        "second": int(b.sum()),
        "both": int((a & b).sum()),
        "only_first": int((a & ~b).sum()),
        "only_second": int((b & ~a).sum()),
    }


def run_verification(
    table: dict, rows, dist, lines_path: str, cfg: dict
) -> dict[str, Any]:
    """Placebo, persistence and height-sensitivity results as a dictionary."""
    verify = cfg["verify"]
    tile, canopy = table["tile"][rows], table["canopy_share"][rows]
    x, y = table["x"][rows], table["y"][rows]
    flags = {e: epoch_flags(table, rows, e, cfg) for e in cfg["epochs"]}
    out: dict[str, Any] = {"real": {}, "placebo": [], "sensitivity": {}}
    for epoch in cfg["epochs"]:
        out["real"][epoch] = ratio_row(flags[epoch], dist, tile, canopy, cfg)
    union = line_union(lines_path)
    exclude = dist < verify["placebo_exclude_within_m"]
    for dx, dy in verify["placebo_shifts_m"]:
        shifted = shapely.transform(
            union, lambda c, dx=dx, dy=dy: c + np.array([dx, dy])
        )
        shifted_dist = shapely.distance(shapely.points(x, y), shifted)
        row = {"shift_m": [dx, dy]}
        for epoch in cfg["epochs"]:
            row[epoch] = ratio_row(
                flags[epoch], shifted_dist, tile, canopy, cfg, exclude
            )
        out["placebo"].append(row)
    near = dist < cfg["bands_m"]["near"][1]
    first, second = (flags[e]["isolated"] for e in cfg["epochs"])
    out["persistence_near"] = persistence_counts(first, second, near)
    out["persistence_far"] = persistence_counts(
        first, second, dist > cfg["control_min_distance_m"]
    )
    tall = copy.deepcopy(cfg)
    tall["spike"]["min_max_height_m"] = verify["sensitivity_min_height_m"]
    for epoch in cfg["epochs"]:
        out["sensitivity"][epoch] = ratio_row(
            epoch_flags(table, rows, epoch, tall), dist, tile, canopy, tall
        )
    return out
