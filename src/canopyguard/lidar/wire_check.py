"""Check labels for isolated tall returns that may be wires or towers.

A wire or tower hit is one tall point in a 10 m cell whose neighbours are low.
This module flags such cells in each epoch and compares the flag rate near
power lines with matched cells far from any line. It is a research label
quality check, not a clearance or safety assessment: line positions are
approximate and carry no conductor height.
"""

from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import NDArray

OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def dedupe_labels(table: dict[str, NDArray]) -> tuple[NDArray, NDArray]:
    """Rows of the unique valid cells, and a mask marking disputed overlaps.

    Rule from label_quality_2013-2022.md: per cell keep the tile with the
    highest minimum coverage, then higher total coverage, then lower tile id.
    """
    valid = np.flatnonzero(np.isfinite(table["mean_change"]))
    cell = table["cell_id"][valid]
    start, end = table["valid_start"][valid], table["valid_end"][valid]
    order = np.lexsort(
        (table["tile"][valid], -(start + end), -np.minimum(start, end), cell)
    )
    sorted_cell = cell[order]
    first = np.r_[True, sorted_cell[1:] != sorted_cell[:-1]]
    unique_cells, counts = np.unique(cell, return_counts=True)
    disputed = np.isin(sorted_cell[first], unique_cells[counts > 1])
    return valid[order[first]], disputed


def analysis_rows(table: dict[str, NDArray]) -> tuple[NDArray, int]:
    """Rows of the cells to analyse and how many disputed cells were removed.

    The unique archive carries an `overlap_disputed` flag and one row per cell,
    so use it as is. A raw archive has repeated cells and no flag, so rebuild
    the unique table with the documented rule.
    """
    if "overlap_disputed" in table:
        valid = np.isfinite(table["mean_change"])
        disputed = np.asarray(table["overlap_disputed"], dtype=bool)
        return np.flatnonzero(valid & ~disputed), int((valid & disputed).sum())
    rows, disputed = dedupe_labels(table)
    return rows[~disputed], int(disputed.sum())


def to_grid(
    x: NDArray, y: NDArray, values: NDArray, cell_m: float
) -> tuple[NDArray, NDArray, NDArray]:
    """Place per-cell values on a dense grid; returns grid, column and row."""
    column = np.round(x / cell_m - 0.5).astype(np.int64)
    row = np.round(y / cell_m - 0.5).astype(np.int64)
    column -= column.min() - 1
    row -= row.min() - 1
    grid = np.full((row.max() + 2, column.max() + 2), np.nan, dtype=np.float32)
    grid[row, column] = values
    return grid, column, row


def neighbour_median(
    grid: NDArray, column: NDArray, row: NDArray, min_neighbours: int
) -> NDArray:
    """Median of the 8 neighbours of each cell; NaN with too few valid ones."""
    stack = np.stack(
        [grid[row + dr, column + dc] for dr, dc in OFFSETS], axis=0
    ).astype(np.float32)
    enough = np.isfinite(stack).sum(axis=0) >= min_neighbours
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(stack, axis=0)
    return np.where(enough, median, np.nan)


def flag_spikes(
    top: NDArray, upper: NDArray, median_around: NDArray, spike: dict
) -> tuple[NDArray, NDArray]:
    """Isolated tall flag and the stricter wire-like flag for each cell."""
    with np.errstate(invalid="ignore"):
        isolated = (top >= spike["min_max_height_m"]) & (
            median_around <= spike["max_neighbour_median_m"]
        )
        wire_like = isolated & (top - upper >= spike["wire_like_gap_m"])
    return isolated, wire_like


def strata_keys(
    tile: NDArray, canopy_share: NDArray, valid: NDArray, cfg: dict
) -> NDArray:
    """Integer stratum id from tile, canopy-share bin and valid-fraction bin."""
    share = np.where(
        np.isfinite(canopy_share),
        np.floor(np.nan_to_num(canopy_share) / cfg["canopy_share_bin"]),
        -1,
    ).astype(np.int64)
    vbin = np.digitize(valid, cfg["valid_fraction_edges"]).astype(np.int64)
    _, key = np.unique(
        np.stack([tile, share, vbin], axis=1), axis=0, return_inverse=True
    )
    return key.ravel()


def expected_counts(
    key: NDArray, flag: NDArray, near: NDArray, control: NDArray
) -> tuple[NDArray, NDArray, NDArray]:
    """Per-stratum observed and expected near-line flags, plus stratum of each.

    Expected = control flag rate in the stratum times the near-line cells in it.
    Strata without control cells are dropped so the ratio is only ever taken
    against a real comparison.
    """
    size = key.max() + 1
    near_n = np.bincount(key[near], minlength=size).astype(float)
    ctrl_n = np.bincount(key[control], minlength=size).astype(float)
    near_f = np.bincount(key[near], weights=flag[near], minlength=size)
    ctrl_f = np.bincount(key[control], weights=flag[control], minlength=size)
    usable = (near_n > 0) & (ctrl_n > 0)
    rate = np.divide(ctrl_f, ctrl_n, out=np.zeros(size), where=ctrl_n > 0)
    observed = np.where(usable, near_f, 0.0)
    expected = np.where(usable, rate * near_n, 0.0)
    return observed, expected, np.where(usable, near_n, 0.0)


def tile_bootstrap_ratio(
    tile_of_stratum: NDArray,
    observed: NDArray,
    expected: NDArray,
    reps: int,
    confidence: float,
    seed: int,
) -> tuple[float, float, float]:
    """Observed/expected ratio with a percentile CI from resampling tiles."""
    tiles, inverse = np.unique(tile_of_stratum, return_inverse=True)
    obs_t = np.bincount(inverse, weights=observed, minlength=len(tiles))
    exp_t = np.bincount(inverse, weights=expected, minlength=len(tiles))
    ratio = obs_t.sum() / exp_t.sum() if exp_t.sum() > 0 else np.nan
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(tiles), size=(reps, len(tiles)))
    num, den = obs_t[draws].sum(axis=1), exp_t[draws].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = num / den
    tail = (1.0 - confidence) / 2.0
    low, high = np.nanquantile(boot, [tail, 1.0 - tail])
    return float(ratio), float(low), float(high)
