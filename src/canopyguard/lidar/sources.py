"""Real coverage of a 3DEP Entwine resource, taken from its source manifest.

The bounds in ept.json enclose the octree cube of a work unit, which for an
irregular flight block is far larger than the area flown. The source manifest
lists every delivered file with its own bounds, so the union of those bounds is
the footprint of the acquisition, and the only tiles two epochs can both supply
are the tiles inside both footprints.

Two adjacent work units share a seam of half-overlapping delivery tiles, which
reads as co-coverage until the tile size is compared with the seam width. The
tile list is therefore derived from the manifests rather than from a bounding
box written down by hand.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from canopyguard.lidar.ept import EPT_BASE, box_from_web_mercator
from canopyguard.lidar.tiles import METRES_PER_DEGREE_LATITUDE

Box = tuple[float, float, float, float]


def manifest_url(project: str) -> str:
    """Source manifest URL for a 3DEP project short name."""
    if not project or "/" in project:
        raise ValueError("Project must be a bare 3DEP project name")
    return f"{EPT_BASE}/{project}/ept-sources/manifest.json"


def parse_manifest(payload: Any, min_points: int = 1) -> list[Box]:
    """Geographic box of every delivered file that holds points."""
    if not isinstance(payload, list):
        raise ValueError("A source manifest is a list of entries")

    boxes: list[Box] = []
    for entry in payload:
        bounds = entry.get("bounds") if isinstance(entry, dict) else None
        if not bounds or len(bounds) != 6:
            continue
        if int(entry.get("points", 0)) < min_points:
            continue
        boxes.append(
            box_from_web_mercator(
                (
                    float(bounds[0]),
                    float(bounds[1]),
                    float(bounds[3]),
                    float(bounds[4]),
                )
            )
        )
    if not boxes:
        raise ValueError("No manifest entry carries usable bounds")
    return boxes


def union_box(boxes: list[Box]) -> Box:
    """Smallest box enclosing every box in a footprint."""
    if not boxes:
        raise ValueError("At least one box is required")
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def cell_steps(
    box: Box, tile_size_m: float, cells_per_tile: int
) -> tuple[float, float]:
    """Longitude and latitude step of the assay grid.

    The two steps differ so that a tile is square on the ground rather than
    square in degrees.
    """
    if tile_size_m <= 0:
        raise ValueError("Tile size must be positive")
    if cells_per_tile < 1:
        raise ValueError("A tile needs at least one assay cell per side")

    mean_latitude = math.radians((box[1] + box[3]) / 2.0)
    latitude_step = tile_size_m / METRES_PER_DEGREE_LATITUDE / cells_per_tile
    return latitude_step / math.cos(mean_latitude), latitude_step


def coverage_mask(
    boxes: list[Box], box: Box, steps: tuple[float, float], union: bool = False
) -> NDArray[np.bool_]:
    """Assay cells lying wholly inside at least one delivered file.

    Partial cover is treated as no cover, so a tile assembled from covered
    cells is one the acquisition can supply in full. With `union` a cell is
    covered when its centre lies inside any file, so a cell straddling two
    abutting delivery files counts as covered; interior coverage of a single
    acquisition is then not broken along every delivery boundary.
    """
    west, south, east, north = box
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    longitude_step, latitude_step = steps
    if longitude_step <= 0 or latitude_step <= 0:
        raise ValueError("Assay steps must be positive")

    columns = int(math.floor((east - west) / longitude_step))
    rows = int(math.floor((north - south) / latitude_step))
    mask = np.zeros((max(rows, 0), max(columns, 0)), dtype=bool)
    if mask.size == 0:
        return mask

    shift = 0.5 if union else 0.0
    for left, bottom, right, top in boxes:
        first_column = max(0, math.ceil((left - west) / longitude_step - shift))
        last_column = min(columns, math.floor((right - west) / longitude_step + shift))
        first_row = max(0, math.ceil((bottom - south) / latitude_step - shift))
        last_row = min(rows, math.floor((top - south) / latitude_step + shift))
        if last_column > first_column and last_row > first_row:
            mask[first_row:last_row, first_column:last_column] = True
    return mask


def covered_tiles(
    masks: list[NDArray[np.bool_]],
    box: Box,
    steps: tuple[float, float],
    cells_per_tile: int,
) -> list[Box]:
    """Grid-aligned tiles every footprint covers completely."""
    if not masks:
        raise ValueError("At least one coverage mask is required")
    shapes = {mask.shape for mask in masks}
    if len(shapes) != 1:
        raise ValueError("Coverage masks must share a grid")

    combined = np.logical_and.reduce(masks)
    rows, columns = combined.shape
    longitude_step, latitude_step = steps
    west, south = box[0], box[1]
    side = int(cells_per_tile)

    return [
        (
            west + column * longitude_step,
            south + row * latitude_step,
            west + (column + side) * longitude_step,
            south + (row + side) * latitude_step,
        )
        for row in range(0, rows - side + 1, side)
        for column in range(0, columns - side + 1, side)
        if combined[row : row + side, column : column + side].all()
    ]


def co_covered_tiles(
    footprints: list[list[Box]],
    box: Box,
    tile_size_m: float,
    cells_per_tile: int = 5,
    union: bool = False,
) -> list[Box]:
    """Tiles inside a search box that every acquisition supplies in full."""
    steps = cell_steps(box, tile_size_m, cells_per_tile)
    masks = [coverage_mask(boxes, box, steps, union) for boxes in footprints]
    return covered_tiles(masks, box, steps, cells_per_tile)


def fetch_json(url: str, timeout_s: float = 300.0) -> Any:
    """Retrieve a JSON document.

    This is the only function in the package that needs network access to the
    point-cloud store.
    """
    import json
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def footprint(project: str) -> list[Box]:
    """Delivered-file boxes of a 3DEP project."""
    return parse_manifest(fetch_json(manifest_url(project)))
