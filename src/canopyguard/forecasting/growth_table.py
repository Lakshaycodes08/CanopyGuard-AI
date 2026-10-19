"""Join as-of Landsat features to LiDAR-derived canopy change on one grid.

The LiDAR change columns are labels and a grader only. They never become
predictors; `start_*` columns are kept for stratified error reporting.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

LABEL_COLUMNS = [
    "mean_change",
    "p95_change",
    "mean_start",
    "p95_start",
    "canopy_share",
    "loss_share",
]


def labels_on_pixel_grid(
    labels: dict[str, NDArray],
    grid: tuple[float, float, float, int, int],
    min_cells: int,
) -> pd.DataFrame:
    """Average 10 m label cells inside each Landsat pixel.

    Label coordinates are NAD83(2011) UTM 10N and the grid is WGS84 UTM 10N;
    the two differ by about a metre, small against a 30 m pixel.
    """
    left, top, step, width, height = grid
    column = np.floor((labels["x"] - left) / step).astype(np.int64)
    row = np.floor((top - labels["y"]) / step).astype(np.int64)
    inside = (column >= 0) & (column < width) & (row >= 0) & (row < height)
    ok = inside & np.isfinite(labels["mean_change"]) & np.isfinite(labels["p95_change"])
    flat = row[ok] * int(width) + column[ok]
    count = np.bincount(flat, minlength=int(width) * int(height))
    frame: dict[str, Any] = {"n_cells": count}
    for name in LABEL_COLUMNS:
        total = np.bincount(flat, weights=labels[name][ok], minlength=count.size)
        with np.errstate(divide="ignore", invalid="ignore"):
            frame[name] = total / count
    table = pd.DataFrame(frame)
    table = table[table["n_cells"] >= min_cells]
    table["row"] = table.index // int(width)
    table["col"] = table.index % int(width)
    return table.reset_index(drop=True)


def block_mean(raster: NDArray, factor: int, min_valid_share: float) -> NDArray:
    """Mean over factor-by-factor blocks, NaN where too few pixels are valid."""
    rows = raster.shape[0] // factor * factor
    cols = raster.shape[1] // factor * factor
    tiles = raster[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    valid = np.isfinite(tiles)
    total = np.where(valid, tiles, 0.0).sum(axis=(1, 3))
    count = valid.sum(axis=(1, 3))
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = total / count
    mean[count < min_valid_share * factor * factor] = np.nan
    return mean.astype(np.float32)


def table_at_scale(
    pixels: pd.DataFrame,
    features: dict[str, NDArray],
    factor: int,
    grid: tuple[float, float, float, int, int],
    min_valid_share: float,
) -> pd.DataFrame:
    """Average labels and features to blocks of `factor` Landsat pixels."""
    left, top, step, _, _ = grid
    block_row = pixels["row"].to_numpy() // factor
    block_col = pixels["col"].to_numpy() // factor
    weights = pixels["n_cells"].to_numpy(dtype=np.float64)
    key = pd.DataFrame({"block_row": block_row, "block_col": block_col})
    columns = {"n_cells": pixels["n_cells"]}
    for name in LABEL_COLUMNS:
        columns[name] = pixels[name] * weights
    grouped = pd.DataFrame(columns).join(key).groupby(["block_row", "block_col"])
    sums = grouped.sum()
    table = sums[["n_cells"]].copy()
    for name in LABEL_COLUMNS:
        table[name] = sums[name] / sums["n_cells"]
    table["n_pixels"] = grouped.size()
    table = table[table["n_pixels"] >= min_valid_share * factor * factor]
    table = table.reset_index()
    block_rasters = {
        name: block_mean(raster, factor, min_valid_share)
        for name, raster in features.items()
    }
    shape = next(iter(block_rasters.values())).shape
    # Partial blocks at the raster edge have no feature block; drop them.
    table = table[(table["block_row"] < shape[0]) & (table["block_col"] < shape[1])]
    table = table.reset_index(drop=True)
    rows = table["block_row"].to_numpy()
    cols = table["block_col"].to_numpy()
    for name, block in block_rasters.items():
        table[name] = block[rows, cols]
    size = step * factor
    table["x"] = left + (cols + 0.5) * size
    table["y"] = top - (rows + 0.5) * size
    return table
