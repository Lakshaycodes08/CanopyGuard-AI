"""Long-baseline canopy height change and its detectability over a tile sample.

The noise floor is measured on the 2022-2023 pair, whose one-year interval
carries little true change. A long-baseline pair is measured here against
that floor. Its own stable-ground check comes from cells low in both epochs,
since the floor of a different pair is an upper bound, not a property of this
one.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.evaluation.detectability import (
    LOD95_Z,
    lod95_at,
    normalised_mad,
    surface_row,
)
from canopyguard.lidar.coreg import (
    align_pooled,
    apply_horizontal_shift,
    apply_shift,
    residual_rmse,
)
from canopyguard.lidar.difference import apply_mask, difference_ladder
from canopyguard.lidar.noise_floor import (
    canopy_height,
    height_summary,
    load_pairs,
    pool_ladder,
)


def _pair_grids(
    first: ArrayLike, second: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    top = np.asarray(first, dtype=np.float64)
    bottom = np.asarray(second, dtype=np.float64)
    if top.shape != bottom.shape:
        raise ValueError("Both epochs must share a grid")
    return top, bottom, np.isfinite(top) & np.isfinite(bottom)


def pair_epochs(
    config: dict[str, Any], pair: list[str] | tuple[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Configured epochs of a change pair, earlier first."""
    by_name = {epoch["name"]: epoch for epoch in config["epochs"]}
    missing = [name for name in pair if name not in by_name]
    if missing:
        raise ValueError("No epoch named: " + ", ".join(missing))
    first, second = (by_name[name] for name in pair)
    return first, second


def baseline_years(start: str, end: str) -> float:
    """Interval between two acquisition start dates in years."""
    days = (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
    if days <= 0:
        raise ValueError("The later epoch must start after the earlier one")
    return days / 365.25


def bare_mask(
    first: ArrayLike, second: ArrayLike, max_height_m: float
) -> NDArray[np.bool_]:
    """Cells below the bare-ground height in both epochs."""
    top, bottom, valid = _pair_grids(first, second)
    with np.errstate(invalid="ignore"):
        return valid & (top < max_height_m) & (bottom < max_height_m)


def canopy_mask(
    first: ArrayLike, second: ArrayLike, min_height_m: float
) -> NDArray[np.bool_]:
    """Cells whose height averaged over the two epochs reaches the canopy height."""
    top, bottom, valid = _pair_grids(first, second)
    with np.errstate(invalid="ignore"):
        return valid & ((top + bottom) / 2.0 >= min_height_m)


def disturbed_mask(
    first: ArrayLike, second: ArrayLike, limit_m: float
) -> NDArray[np.bool_]:
    """Cells whose height changes by more than the disturbance limit."""
    if limit_m <= 0:
        raise ValueError("Disturbance limit must be positive")
    top, bottom, valid = _pair_grids(first, second)
    with np.errstate(invalid="ignore"):
        return valid & (np.abs(bottom - top) > limit_m)


def loss_mask(
    first: ArrayLike, second: ArrayLike, limit_m: float
) -> NDArray[np.bool_]:
    """Cells whose height falls by more than the disturbance limit."""
    if limit_m <= 0:
        raise ValueError("Disturbance limit must be positive")
    top, bottom, valid = _pair_grids(first, second)
    with np.errstate(invalid="ignore"):
        return valid & (bottom - top < -limit_m)


def canopy_stratum(
    first: ArrayLike, second: ArrayLike, min_height_m: float, limit_m: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Both epochs blanked outside canopy cells that did not lose height.

    Only losses are removed. Over a multi-year baseline, growth beyond the
    disturbance limit is part of the signal being measured.
    """
    keep = canopy_mask(first, second, min_height_m) & ~loss_mask(
        first, second, limit_m
    )
    return apply_mask(first, keep), apply_mask(second, keep)


def terrain_agreement(
    pairs: list[tuple[ArrayLike, ArrayLike]],
) -> dict[str, float]:
    """Pooled agreement of two terrain surfaces on cells valid in both.

    The scale is the slope of the first surface fitted against the second and
    exposes a unit fault. A constant offset is reported but not judged: it is
    a datum difference, it is solved by co-registration, and it cancels inside
    each epoch's canopy height.
    """
    firsts, seconds = [], []
    for first, second in pairs:
        top, bottom, valid = _pair_grids(first, second)
        firsts.append(top[valid])
        seconds.append(bottom[valid])
    a = np.concatenate(firsts) if firsts else np.array([])
    b = np.concatenate(seconds) if seconds else np.array([])
    if a.size == 0:
        raise ValueError("No terrain cell is valid in both epochs")
    scale = float(np.polyfit(b, a, 1)[0]) if np.ptp(b) > 0 else float("nan")
    return {
        "cells": float(a.size),
        "median_first_m": float(np.median(a)),
        "median_second_m": float(np.median(b)),
        "scale": scale,
        "offset_m": float(np.median(a - b)),
    }


def bare_floor(change: ArrayLike, bare: ArrayLike) -> dict[str, float]:
    """Location and spread of the change on cells bare in both epochs.

    Ground carrying nothing in either epoch should not change, so the mean is
    the bias of the pair and the spread is its own floor at the base scale.
    """
    values = np.asarray(change, dtype=np.float64)
    selected = np.asarray(bare, dtype=bool)
    if values.shape != selected.shape:
        raise ValueError("Mask must match the grid shape")
    values = values[selected & np.isfinite(values)]
    if values.size < 2:
        return {
            "cells": float(values.size),
            "mean_m": float("nan"),
            "median_m": float("nan"),
            "nmad_m": float("nan"),
        }
    return {
        "cells": float(values.size),
        "mean_m": float(np.mean(values)),
        "median_m": float(np.median(values)),
        "nmad_m": normalised_mad(values),
    }


def disturbance(change: ArrayLike, limit_m: float) -> dict[str, float]:
    """Shares of valid cells losing or gaining more than the limit."""
    if limit_m <= 0:
        raise ValueError("Disturbance limit must be positive")
    values = np.asarray(change, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    count = values.size
    return {
        "limit_m": float(limit_m),
        "valid_cells": float(count),
        "loss_fraction": float(np.mean(values < -limit_m)) if count else 0.0,
        "gain_fraction": float(np.mean(values > limit_m)) if count else 0.0,
    }


def change_row(
    delta: ArrayLike,
    sigma: float,
    scale_m: float,
    years: float,
    min_cells: int = 0,
) -> dict[str, float]:
    """Detectability row of one stratum at one scale, with the signed median.

    The signal of `surface_row` is the median absolute change, which cannot
    tell growth from loss, so the signed median is carried beside it.
    """
    values = np.asarray(delta, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size < 2:
        return {
            "scale_m": float(scale_m),
            "baseline_years": float(years),
            "sigma_m": float(sigma),
            "lod95_m": float(LOD95_Z * sigma),
            "signal_m": float("nan"),
            "snr": float("nan"),
            "annual_rate_m": float("nan"),
            "detectable_fraction": float("nan"),
            "cells": float(values.size),
            "median_change_m": float("nan"),
            "admitted": False,
        }
    row = surface_row(values, sigma, scale_m, years)
    row["median_change_m"] = float(np.median(values))
    row["admitted"] = bool(values.size >= min_cells)
    return row


def surface_table(
    all_by_scale: dict[float, ArrayLike],
    canopy_by_scale: dict[float, ArrayLike],
    measured: dict[str, Any],
    years: float,
    min_cells: int = 0,
) -> list[dict[str, Any]]:
    """Rows for all valid cells and for canopy cells at each scale.

    The spread at each scale is the measured noise floor, taken from the
    measured limit of detection where the scale was admitted and from the
    decay law otherwise.
    """
    table = []
    for scale in sorted(all_by_scale):
        limit = lod95_at(scale, measured)
        sigma = limit / LOD95_Z
        table.append(
            {
                "scale_m": float(scale),
                "lod95_m": float(limit),
                "all": change_row(all_by_scale[scale], sigma, scale, years, min_cells),
                "canopy": change_row(
                    canopy_by_scale.get(scale, np.array([])),
                    sigma,
                    scale,
                    years,
                    min_cells,
                ),
            }
        )
    return table


def measure_pair(
    plan: dict[str, Any],
    out_dir: str | Path,
    pair: list[str] | tuple[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Co-register a long-baseline pair as one block and measure its change.

    The noise-floor pair bias is not removed here. It belongs to that pair,
    and this pair carries its own check on bare ground.
    """
    from canopyguard.lidar.gridio import write_grid

    settings = config["coregistration"]
    resolution = config["chm"]["resolution_m"]
    aggregation = config["aggregation"]
    rules = config["change"]
    epochs = (str(pair[0]), str(pair[1]))
    first_epoch, second_epoch = pair_epochs(config, epochs)
    years = baseline_years(first_epoch["start"], second_epoch["start"])

    loaded, verdicts = load_pairs(
        plan, out_dir, epochs, config["noise_floor"]["tile_admission"]
    )
    if not loaded:
        raise ValueError("No tile passed admission")

    check = terrain_agreement([tile["terrain"] for tile in loaded])
    if abs(check["scale"] - 1.0) > float(rules["max_terrain_scale_error"]):
        raise ValueError(
            "Terrain of the two epochs differs in scale before co-registration: "
            f"fitted scale {check['scale']:.4f}, offset {check['offset_m']:.2f} m. "
            "A scale near 3.2808 indicates elevations stored in feet."
        )

    shift = align_pooled(
        [tile["terrain"] for tile in loaded],
        resolution,
        settings["min_slope_deg"],
        settings["max_slope_deg"],
        settings["max_iterations"],
        settings["convergence_tolerance_m"],
    )

    limit = float(rules["disturbance_limit_m"])
    changes: list[NDArray[np.float64]] = []
    bare: list[NDArray[np.bool_]] = []
    heights: list[dict[str, Any]] = []
    deltas_all: list[dict[float, NDArray[np.float64]]] = []
    deltas_canopy: list[dict[float, NDArray[np.float64]]] = []
    for tile in loaded:
        terrain_a, terrain_b = tile["terrain"]
        surface_a, surface_b = tile["surface"]
        first, second = tile["paths"]

        height_a = canopy_height(surface_a, terrain_a, config)
        height_b = apply_horizontal_shift(
            canopy_height(surface_b, terrain_b, config), shift, resolution
        )
        write_grid(first["chm"], height_a, tile["profile"])
        write_grid(second["chm"], height_b, tile["profile"])
        heights.append(
            {
                "tile": float(tile["index"]),
                epochs[0]: height_summary(height_a),
                epochs[1]: height_summary(height_b),
                "rmse_before_m": residual_rmse(terrain_a, terrain_b, resolution),
                "rmse_after_m": residual_rmse(
                    terrain_a, apply_shift(terrain_b, shift, resolution), resolution
                ),
            }
        )

        changes.append((height_b - height_a).ravel())
        bare.append(
            bare_mask(height_a, height_b, float(rules["bare_max_height_m"])).ravel()
        )
        deltas_all.append(
            difference_ladder(
                height_a,
                height_b,
                resolution,
                aggregation["scales_m"],
                aggregation["min_valid_fraction"],
            )
        )
        canopy_a, canopy_b = canopy_stratum(
            height_a, height_b, float(rules["canopy_min_height_m"]), limit
        )
        deltas_canopy.append(
            difference_ladder(
                canopy_a,
                canopy_b,
                resolution,
                aggregation["scales_m"],
                aggregation["min_valid_fraction"],
            )
        )

    change = np.concatenate(changes)
    return {
        "pair": list(epochs),
        "baseline_years": years,
        "terrain_check": check,
        "shift": shift,
        "tiles": verdicts,
        "heights": heights,
        "bare_floor": bare_floor(change, np.concatenate(bare)),
        "disturbance": disturbance(change, limit),
        "surface": surface_table(
            pool_ladder(deltas_all),
            pool_ladder(deltas_canopy),
            config["noise_floor"]["measured"],
            years,
            int(aggregation["min_cells_per_scale"]),
        ),
    }
