"""Ground and surface statistics of point clouds on a grid of square tiles.

Each tile is cut into square cells. A cell keeps the number of returns, the
mean ground elevation, and the highest return above the ground classes. Height
above ground is the highest return minus the mean ground elevation of the same
cell. This is a coarse stand-in for a canopy height model: it uses the
provider's ground class and does not re-classify ground, so it is for judging
coverage and canopy extent, not for measuring change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from canopyguard.lidar.ept import WEB_MERCATOR_RADIUS_M

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class PointRules:
    """Classes and flags that decide which returns count."""

    noise_classes: tuple[int, ...]
    water_class: int
    ground_class: int
    excluded_flag_bits: int


class TileGrid(NamedTuple):
    """Tiles that sit on one regular lon/lat grid."""

    west: float
    south: float
    lon_step: float
    lat_step: float
    cells: int
    lookup: np.ndarray
    tiles: list[Box]


class TileStats:
    """Running per-cell counts and sums for every tile of one epoch."""

    def __init__(self, tile_count: int, cells: int) -> None:
        shape = (tile_count, cells, cells)
        self.point_count = np.zeros(shape, dtype=np.int64)
        self.ground_count = np.zeros(shape, dtype=np.int64)
        self.ground_sum = np.zeros(shape, dtype=np.float64)
        self.surface_max = np.full(shape, -np.inf, dtype=np.float64)


def make_tile_grid(tiles: list[Box], cells: int) -> TileGrid:
    """Index tiles that share one lon/lat step so points can be binned fast."""
    if not tiles:
        raise ValueError("At least one tile is required")
    if cells < 1:
        raise ValueError("A tile needs at least one cell per side")
    lon_step = tiles[0][2] - tiles[0][0]
    lat_step = tiles[0][3] - tiles[0][1]
    west = min(tile[0] for tile in tiles)
    south = min(tile[1] for tile in tiles)
    columns = [round((tile[0] - west) / lon_step) for tile in tiles]
    rows = [round((tile[1] - south) / lat_step) for tile in tiles]
    lookup = np.full((max(rows) + 1, max(columns) + 1), -1, dtype=np.int64)
    for index, (row, column) in enumerate(zip(rows, columns, strict=True)):
        lookup[row, column] = index
    return TileGrid(west, south, lon_step, lat_step, cells, lookup, list(tiles))


def mercator_to_lonlat(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert EPSG:3857 arrays to longitude and latitude in degrees."""
    longitude = np.degrees(x / WEB_MERCATOR_RADIUS_M)
    latitude = np.degrees(
        2.0 * np.arctan(np.exp(y / WEB_MERCATOR_RADIUS_M)) - math.pi / 2
    )
    return longitude, latitude


def locate(
    grid: TileGrid, longitude: np.ndarray, latitude: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tile index (-1 outside every tile) and cell row and column of each point."""
    fx = (longitude - grid.west) / grid.lon_step
    fy = (latitude - grid.south) / grid.lat_step
    column, row = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    rows, columns = grid.lookup.shape
    inside = (column >= 0) & (column < columns) & (row >= 0) & (row < rows)
    tile = np.full(len(longitude), -1, dtype=np.int64)
    tile[inside] = grid.lookup[row[inside], column[inside]]
    cell_column = np.clip(np.floor((fx - column) * grid.cells), 0, grid.cells - 1)
    cell_row = np.clip(np.floor((fy - row) * grid.cells), 0, grid.cells - 1)
    return tile, cell_row.astype(np.int64), cell_column.astype(np.int64)


def add_points(
    stats: TileStats, grid: TileGrid, points: dict[str, np.ndarray], rules: PointRules
) -> int:
    """Add the countable returns of one node to the statistics; return how many."""
    longitude, latitude = mercator_to_lonlat(points["x"], points["y"])
    tile, row, column = locate(grid, longitude, latitude)
    classes = points["classification"]
    drop = np.isin(classes, [*rules.noise_classes, rules.water_class])
    drop |= (points["flags"] & rules.excluded_flag_bits) != 0
    keep = (tile >= 0) & ~drop
    if not keep.any():
        return 0

    flat = (tile[keep] * grid.cells + row[keep]) * grid.cells + column[keep]
    z = points["z"][keep]
    ground = classes[keep] == rules.ground_class
    size = stats.point_count.size
    stats.point_count.reshape(-1)[:] += np.bincount(flat, minlength=size)
    stats.ground_count.reshape(-1)[:] += np.bincount(flat[ground], minlength=size)
    stats.ground_sum.reshape(-1)[:] += np.bincount(flat[ground], z[ground], size)
    np.maximum.at(stats.surface_max.reshape(-1), flat[~ground], z[~ground])
    return int(keep.sum())


def ground_surface(stats: TileStats) -> np.ndarray:
    """Mean ground elevation per cell, NaN where the cell has no ground return."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(
            stats.ground_count > 0, stats.ground_sum / stats.ground_count, np.nan
        )


def heights_above_ground(stats: TileStats) -> np.ndarray:
    """Highest non-ground return above the mean ground, NaN if either is missing."""
    ground = ground_surface(stats)
    top = np.where(np.isfinite(stats.surface_max), stats.surface_max, np.nan)
    return np.maximum(top - ground, 0.0)


def tile_validity(
    stats: TileStats, min_cell_fraction: float, min_ground_fraction: float
) -> dict[str, np.ndarray]:
    """Share of cells holding returns and ground returns, and the valid flag."""
    cell_fraction = (stats.point_count > 0).mean(axis=(1, 2))
    ground_fraction = (stats.ground_count > 0).mean(axis=(1, 2))
    return {
        "cell_fraction": cell_fraction,
        "ground_fraction": ground_fraction,
        "valid": (cell_fraction >= min_cell_fraction)
        & (ground_fraction >= min_ground_fraction),
    }


def slope_degrees(ground: np.ndarray, cell_m: float) -> np.ndarray:
    """Terrain slope per cell from the mean ground surface, NaN where unknown."""
    with np.errstate(invalid="ignore"):
        d_row, d_column = np.gradient(ground, cell_m, axis=(1, 2))
        return np.degrees(np.arctan(np.hypot(d_row, d_column)))


def cell_centres(grid: TileGrid) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude of every cell centre, shaped like the statistics."""
    count, cells = len(grid.tiles), grid.cells
    steps = (np.arange(cells) + 0.5) / cells
    longitude = np.empty((count, cells, cells))
    latitude = np.empty((count, cells, cells))
    for index, (west, south, east, north) in enumerate(grid.tiles):
        longitude[index] = west + (east - west) * steps[None, :]
        latitude[index] = south + (north - south) * steps[:, None]
    return longitude, latitude
