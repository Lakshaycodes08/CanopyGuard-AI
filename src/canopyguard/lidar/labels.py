"""Cell labels on the global grid from a co-registered canopy height pair.

A label cell is a square of `cell_m` metres whose edges are multiples of
`cell_m` in the working frame, so a cell identifier is the same in every tile
and every run. Clearance risk depends on the tallest crowns, so the upper
percentile and the maximum are carried alongside the mean.
"""

from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import ArrayLike, NDArray

CELL_ID_ROW_BASE = 10_000_000


def cell_id(column: ArrayLike, row: ArrayLike) -> NDArray[np.int64]:
    """Stable identifier from global column and row indices."""
    c = np.asarray(column, dtype=np.int64)
    r = np.asarray(row, dtype=np.int64)
    if np.any(r < 0) or np.any(r >= CELL_ID_ROW_BASE) or np.any(c < 0):
        raise ValueError("Cell indices out of range")
    return c * CELL_ID_ROW_BASE + r


def _blocks(grid: NDArray[np.float64], factor: int) -> NDArray[np.float64]:
    rows, cols = grid.shape[0] // factor, grid.shape[1] // factor
    trimmed = grid[: rows * factor, : cols * factor]
    return (
        trimmed.reshape(rows, factor, cols, factor)
        .transpose(0, 2, 1, 3)
        .reshape(rows, cols, factor * factor)
    )


def _statistics(
    blocks: NDArray[np.float64], min_valid: float, percentile: float
) -> dict[str, NDArray[np.float64]]:
    valid = np.isfinite(blocks).mean(axis=-1)
    keep = valid >= min_valid
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(blocks, axis=-1)
        upper = np.nanpercentile(blocks, percentile, axis=-1)
        top = np.nanmax(blocks, axis=-1)
    return {
        "valid": valid,
        "mean": np.where(keep, mean, np.nan),
        "p95": np.where(keep, upper, np.nan),
        "max": np.where(keep, top, np.nan),
    }


def cell_labels(
    start: ArrayLike,
    end: ArrayLike,
    transform: ArrayLike,
    cell_m: float = 10.0,
    min_valid_fraction: float = 0.5,
    canopy_min_height_m: float = 2.0,
    loss_limit_m: float = 3.0,
    percentile: float = 95.0,
) -> dict[str, NDArray]:
    """One row per global cell: heights at both epochs, their change, shares.

    `transform` is the north-up affine transform (a, b, c, d, e, f) of the
    raster. Its upper left corner must lie on the global grid.
    """
    first = np.asarray(start, dtype=np.float64)
    second = np.asarray(end, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("Both epochs must share a grid")
    a, b, left, d, e, top = (float(v) for v in list(transform)[:6])
    if b or d or a <= 0 or e >= 0 or abs(a + e) > 1e-9:
        raise ValueError("Raster must be north up with square cells")
    ratio = cell_m / a
    factor = int(round(ratio))
    if factor < 1 or abs(ratio - factor) > 1e-9:
        raise ValueError("Cell size must be a whole multiple of the resolution")
    if (
        abs(left / cell_m - round(left / cell_m)) > 1e-6
        or abs(top / cell_m - round(top / cell_m)) > 1e-6
    ):
        raise ValueError("Raster corner is not on the global grid")
    if first.shape[0] < factor or first.shape[1] < factor:
        raise ValueError("Raster is smaller than one cell")

    s = _statistics(_blocks(first, factor), min_valid_fraction, percentile)
    t = _statistics(_blocks(second, factor), min_valid_fraction, percentile)
    both = np.isfinite(first) & np.isfinite(second)
    with np.errstate(invalid="ignore"):
        loss = both & (second - first < -loss_limit_m)
        canopy = both & (first >= canopy_min_height_m)
    counts = _blocks(both.astype(np.float64), factor).sum(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        loss_share = np.where(
            counts > 0,
            _blocks(loss.astype(np.float64), factor).sum(-1) / counts,
            np.nan,
        )
        canopy_share = np.where(
            counts > 0,
            _blocks(canopy.astype(np.float64), factor).sum(-1) / counts,
            np.nan,
        )

    rows, cols = s["mean"].shape
    column = int(round(left / cell_m)) + np.arange(cols)
    row = int(round(top / cell_m)) - 1 - np.arange(rows)
    column_grid, row_grid = np.meshgrid(column, row)
    table = {
        "cell_id": cell_id(column_grid, row_grid).ravel(),
        "x": ((column_grid + 0.5) * cell_m).ravel().astype(np.float64),
        "y": ((row_grid + 0.5) * cell_m).ravel().astype(np.float64),
        "valid_start": s["valid"].ravel(),
        "valid_end": t["valid"].ravel(),
        "loss_share": loss_share.ravel(),
        "canopy_share": canopy_share.ravel(),
    }
    for key in ("mean", "p95", "max"):
        table[f"{key}_start"] = s[key].ravel()
        table[f"{key}_end"] = t[key].ravel()
        table[f"{key}_change"] = (t[key] - s[key]).ravel()
    return table
