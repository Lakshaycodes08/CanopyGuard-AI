"""Cell table joining LiDAR canopy change to terrain and Landsat predictors.

Every quantity is aggregated onto one block grid: a block of the 1 m canopy
height grid equal in size to a Landsat cell. The target is the change of the
block mean canopy height, the quantity the detectability surface reports at
the same scale.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.lidar.raster import block_reduce, slope_aspect


def _fraction(
    mask: NDArray[np.bool_], valid: NDArray[np.bool_], factor: int
) -> NDArray[np.float64]:
    rows = mask.shape[0] // factor
    columns = mask.shape[1] // factor
    shape = (rows, factor, columns, factor)
    hits = mask[: rows * factor, : columns * factor].reshape(shape).sum(axis=(1, 3))
    counts = valid[: rows * factor, : columns * factor].reshape(shape).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(counts > 0, hits / counts, np.nan)


def cell_targets(
    start: ArrayLike,
    end: ArrayLike,
    factor: int,
    min_valid_fraction: float = 0.5,
    canopy_min_height_m: float = 2.0,
    loss_limit_m: float = 3.0,
) -> dict[str, NDArray[np.float64]]:
    """Block start height, end height, change, canopy share and loss share."""
    first = np.asarray(start, dtype=np.float64)
    second = np.asarray(end, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("Both epochs must share a grid")
    start_h = block_reduce(first, factor, "mean", min_valid_fraction)
    end_h = block_reduce(second, factor, "mean", min_valid_fraction)
    both = np.isfinite(first) & np.isfinite(second)
    with np.errstate(invalid="ignore"):
        canopy = both & (first >= canopy_min_height_m)
        loss = both & (second - first < -loss_limit_m)
    return {
        "start_h": start_h,
        "end_h": end_h,
        "change": end_h - start_h,
        "canopy_fraction": _fraction(canopy, both, factor),
        "loss_fraction": _fraction(loss, both, factor),
    }


def terrain_features(
    elevation: ArrayLike, factor: int, resolution_m: float
) -> dict[str, NDArray[np.float64]]:
    """Block elevation with slope and aspect taken at the block scale."""
    mean = block_reduce(np.asarray(elevation, dtype=np.float64), factor, "mean", 0.5)
    slope, aspect = slope_aspect(mean, resolution_m * factor)
    return {
        "elevation": mean,
        "slope_deg": np.degrees(slope),
        "northness": np.cos(aspect),
        "eastness": np.sin(aspect),
    }


def trend(values_by_year: dict[int, NDArray[np.float64]]) -> NDArray[np.float64]:
    """Per-cell least-squares slope against year, ignoring missing years.

    Cells with fewer than three observed years are not-a-number.
    """
    years = sorted(values_by_year)
    if not years:
        raise ValueError("At least one year is required")
    stack = np.stack([np.asarray(values_by_year[y], dtype=np.float64) for y in years])
    time = np.asarray(years, dtype=np.float64).reshape(-1, *([1] * (stack.ndim - 1)))
    observed = np.isfinite(stack)
    count = observed.sum(axis=0)
    t = np.where(observed, time, 0.0)
    v = np.where(observed, stack, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        t_mean = t.sum(axis=0) / count
        v_mean = v.sum(axis=0) / count
        dt = np.where(observed, time - t_mean, 0.0)
        dv = np.where(observed, stack - v_mean, 0.0)
        slope = (dt * dv).sum(axis=0) / (dt * dt).sum(axis=0)
    return np.where(count >= 3, slope, np.nan)


def optical_features(
    stacks: dict[int, dict[str, NDArray[np.float64]]],
    first_year: int,
    last_year: int,
    trend_bands: tuple[str, ...] = ("ndvi", "nbr", "ndmi"),
) -> dict[str, NDArray[np.float64]]:
    """Start and end values, their difference, and trends of selected indices."""
    for year in (first_year, last_year):
        if year not in stacks:
            raise ValueError(f"No composite for {year}")
    features: dict[str, NDArray[np.float64]] = {}
    for band in stacks[first_year]:
        if band == "clear_count":
            continue
        start = stacks[first_year][band]
        end = stacks[last_year][band]
        features[f"{band}_start"] = start
        features[f"{band}_end"] = end
        features[f"{band}_diff"] = end - start
    for band in trend_bands:
        features[f"{band}_trend"] = trend(
            {
                year: stack[band]
                for year, stack in stacks.items()
                if first_year <= year <= last_year and band in stack
            }
        )
    return features


def flatten(
    tile: int, columns: dict[str, NDArray[np.float64]]
) -> dict[str, NDArray[np.float64]]:
    """One row per block cell, with tile, row and column identifiers."""
    shapes = {np.asarray(values).shape for values in columns.values()}
    if len(shapes) != 1:
        raise ValueError("All columns must share a grid: " + str(sorted(shapes)))
    (shape,) = shapes
    rows, cols = np.indices(shape)
    table = {
        name: np.asarray(values, dtype=np.float64).ravel()
        for name, values in columns.items()
    }
    table["tile"] = np.full(rows.size, float(tile))
    table["row"] = rows.ravel().astype(np.float64)
    table["col"] = cols.ravel().astype(np.float64)
    return table
