"""Grid operations shared by the co-registration and differencing stages."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

STATISTICS = ("mean", "median", "p95", "max")


def _as_grid(array: ArrayLike) -> NDArray[np.float64]:
    grid = np.asarray(array, dtype=np.float64)
    if grid.ndim != 2:
        raise ValueError("Expected a two dimensional grid")
    return grid


def block_reduce(
    array: ArrayLike,
    factor: int,
    statistic: str = "mean",
    min_valid_fraction: float = 0.5,
) -> NDArray[np.float64]:
    """Aggregate a grid by an integer factor, ignoring no-data cells.

    Output cells whose valid input fraction falls below the threshold are set
    to no-data rather than reported from a partial sample.
    """
    if factor < 1:
        raise ValueError("Aggregation factor must be at least one")
    if statistic not in STATISTICS:
        raise ValueError(f"Statistic must be one of {STATISTICS}")
    if not 0.0 <= min_valid_fraction <= 1.0:
        raise ValueError("Valid fraction must lie in [0, 1]")

    grid = _as_grid(array)
    if factor == 1:
        return grid.copy()

    rows = grid.shape[0] // factor
    columns = grid.shape[1] // factor
    if rows == 0 or columns == 0:
        raise ValueError("Aggregation factor exceeds the grid extent")

    blocks = grid[: rows * factor, : columns * factor].reshape(
        rows, factor, columns, factor
    )
    valid = np.isfinite(blocks).mean(axis=(1, 3))
    reduced = _reduce_blocks(blocks, statistic)
    return np.where(valid >= min_valid_fraction, reduced, np.nan)


def _reduce_blocks(blocks: NDArray[np.float64], statistic: str) -> NDArray[np.float64]:
    axes = (1, 3)
    with np.errstate(invalid="ignore"):
        if statistic == "mean":
            return np.nanmean(blocks, axis=axes)
        if statistic == "median":
            return np.nanmedian(blocks, axis=axes)
        if statistic == "max":
            return np.nanmax(blocks, axis=axes)
        return np.nanpercentile(blocks, 95, axis=axes)


def slope_aspect(
    elevation: ArrayLike, resolution: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return slope in radians and downhill aspect clockwise from north.

    The grid is north up, so the row index increases southward and the north
    gradient is the negated row gradient.
    """
    if resolution <= 0:
        raise ValueError("Resolution must be positive")

    grid = _as_grid(elevation)
    row_gradient, column_gradient = np.gradient(grid, resolution)
    east = column_gradient
    north = -row_gradient
    slope = np.arctan(np.hypot(east, north))
    aspect = np.mod(np.arctan2(-east, -north), 2.0 * np.pi)
    return slope, aspect


def shift_bilinear(
    array: ArrayLike, dx_m: float, dy_m: float, resolution: float
) -> NDArray[np.float64]:
    """Resample a grid so the output at a location holds the input at an offset.

    Output cell (x, y) takes the input value at (x + dx, y + dy). Cells whose
    source falls outside the grid become no-data.
    """
    if resolution <= 0:
        raise ValueError("Resolution must be positive")

    grid = _as_grid(array)
    rows, columns = grid.shape
    row_index, column_index = np.meshgrid(
        np.arange(rows, dtype=np.float64),
        np.arange(columns, dtype=np.float64),
        indexing="ij",
    )
    source_row = row_index - dy_m / resolution
    source_column = column_index + dx_m / resolution
    return _bilinear_sample(grid, source_row, source_column)


def _bilinear_sample(
    grid: NDArray[np.float64],
    row: NDArray[np.float64],
    column: NDArray[np.float64],
) -> NDArray[np.float64]:
    rows, columns = grid.shape
    row_floor = np.floor(row).astype(np.int64)
    column_floor = np.floor(column).astype(np.int64)
    inside = (
        (row_floor >= 0)
        & (column_floor >= 0)
        & (row_floor < rows - 1)
        & (column_floor < columns - 1)
    )

    clipped_row = np.clip(row_floor, 0, rows - 2)
    clipped_column = np.clip(column_floor, 0, columns - 2)
    row_weight = row - clipped_row
    column_weight = column - clipped_column

    top = (
        grid[clipped_row, clipped_column] * (1.0 - column_weight)
        + grid[clipped_row, clipped_column + 1] * column_weight
    )
    bottom = (
        grid[clipped_row + 1, clipped_column] * (1.0 - column_weight)
        + grid[clipped_row + 1, clipped_column + 1] * column_weight
    )
    sampled = top * (1.0 - row_weight) + bottom * row_weight
    return np.where(inside, sampled, np.nan)
