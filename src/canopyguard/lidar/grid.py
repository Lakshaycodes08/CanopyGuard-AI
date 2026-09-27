"""Fixed pixel grids shared by both epochs of a tile.

A raster writer that infers its grid from the extent of the points it is given
assigns each epoch a different origin and size, and two such rasters cannot be
differenced. Every epoch of a tile is therefore written onto a grid derived
from the tile box alone, snapped outward to a multiple of the resolution.
"""

from __future__ import annotations

import math
from typing import Any

Box = tuple[float, float, float, float]


def project_box(box: Box, target_crs: str, samples_per_edge: int = 21) -> Box:
    """Bounding box of a geographic box in a projected frame.

    A rectangle in one frame is not a rectangle in another, so the edges are
    sampled rather than only the corners.
    """
    from pyproj import Transformer

    west, south, east, north = box
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    if samples_per_edge < 2:
        raise ValueError("An edge needs at least two samples")

    steps = [index / (samples_per_edge - 1) for index in range(samples_per_edge)]
    longitudes = [west + step * (east - west) for step in steps]
    latitudes = [south + step * (north - south) for step in steps]
    ring_x = longitudes + [east] * samples_per_edge + longitudes
    ring_y = [south] * samples_per_edge + latitudes + [north] * samples_per_edge
    ring_x += [west] * samples_per_edge
    ring_y += latitudes

    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    xs, ys = transformer.transform(ring_x, ring_y)
    return (min(xs), min(ys), max(xs), max(ys))


def grid_geometry(
    box: Box, resolution_m: float, snap_m: float | None = None
) -> dict[str, Any]:
    """Origin, width and height of the grid covering a projected box.

    The origin is the lower left corner, which is what the raster writer takes.
    Origin and extent are snapped outward to a multiple of `snap_m` (by default
    the resolution), so any two tiles and any two epochs share cell boundaries
    exactly, and with a snap that is a multiple of every aggregation cell the
    aggregated cells of every tile fall on one global grid.
    """
    min_x, min_y, max_x, max_y = box
    if min_x >= max_x or min_y >= max_y:
        raise ValueError("Require min < max on both axes")
    if resolution_m <= 0:
        raise ValueError("Resolution must be positive")
    snap = float(snap_m) if snap_m else float(resolution_m)
    ratio = snap / resolution_m
    if snap <= 0 or abs(ratio - round(ratio)) > 1e-9:
        raise ValueError("Snap must be a positive multiple of the resolution")

    origin_x = math.floor(min_x / snap) * snap
    origin_y = math.floor(min_y / snap) * snap
    extent_x = math.ceil((max_x - origin_x) / snap) * snap
    extent_y = math.ceil((max_y - origin_y) / snap) * snap
    return {
        "origin_x": float(origin_x),
        "origin_y": float(origin_y),
        "width": int(round(extent_x / resolution_m)),
        "height": int(round(extent_y / resolution_m)),
        "resolution_m": float(resolution_m),
    }


def grid_box(grid: dict[str, Any]) -> Box:
    """Projected extent a grid covers."""
    resolution = float(grid["resolution_m"])
    return (
        float(grid["origin_x"]),
        float(grid["origin_y"]),
        float(grid["origin_x"]) + int(grid["width"]) * resolution,
        float(grid["origin_y"]) + int(grid["height"]) * resolution,
    )


def tile_grid_geometry(
    box: Box, target_crs: str, resolution_m: float, snap_m: float | None = None
) -> dict[str, Any]:
    """Grid a geographic tile is rasterised onto in the working frame."""
    return grid_geometry(project_box(box, target_crs), resolution_m, snap_m)
