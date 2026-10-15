"""Where two LiDAR acquisitions both deliver files, in km2 and relative to a box.

The footprint of an acquisition is the union of its delivered-file boxes, which
is an upper bound on the ground it covers. Point-level checks refine it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import box as shapely_box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from canopyguard.lidar import sources

Box = tuple[float, float, float, float]
WGS84 = "EPSG:4326"


def footprint_geometry(boxes: list[Box]) -> BaseGeometry:
    """Union of delivered-file boxes as one lon/lat geometry."""
    if not boxes:
        raise ValueError("At least one box is required")
    return unary_union([shapely_box(*box) for box in boxes])


def project(geometry: BaseGeometry, crs: str) -> BaseGeometry:
    """Reproject a lon/lat geometry into a metre-based CRS."""
    transformer = Transformer.from_crs(WGS84, crs, always_xy=True)
    return shapely.transform(
        geometry, lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1]))
    )


def area_km2(geometry: BaseGeometry, crs: str) -> float:
    """Area of a lon/lat geometry in square kilometres."""
    return float(project(geometry, crs).area / 1e6)


def parts(geometry: BaseGeometry) -> list[BaseGeometry]:
    """Separate polygons of a geometry, largest first."""
    pieces = list(getattr(geometry, "geoms", [geometry]))
    return sorted(
        (piece for piece in pieces if not piece.is_empty), key=lambda g: -g.area
    )


def distance_km(geometry: BaseGeometry, bbox: Box, crs: str) -> float:
    """Shortest distance between a geometry and a box, in kilometres."""
    return float(
        project(geometry, crs).distance(project(shapely_box(*bbox), crs)) / 1e3
    )


def within_buffer_km2(
    geometry: BaseGeometry, bbox: Box, buffer_km: float, crs: str
) -> float:
    """Area of a geometry within a distance of a box, in square kilometres."""
    near = project(shapely_box(*bbox), crs).buffer(buffer_km * 1e3)
    return float(project(geometry, crs).intersection(near).area / 1e6)


def overlap_summary(
    first: list[Box],
    second: list[Box],
    study_bbox: Box,
    crs: str,
    buffers_km: list[float],
) -> dict[str, Any]:
    """Footprint areas, shared area, its patches, and where it lies."""
    left, right = footprint_geometry(first), footprint_geometry(second)
    shared = left.intersection(right)
    study = shapely_box(*study_bbox)
    return {
        "first_footprint_km2": area_km2(left, crs),
        "second_footprint_km2": area_km2(right, crs),
        "first_in_study_box_km2": area_km2(left.intersection(study), crs),
        "second_in_study_box_km2": area_km2(right.intersection(study), crs),
        "shared_km2": area_km2(shared, crs),
        "shared_in_study_box_km2": area_km2(shared.intersection(study), crs),
        "shared_distance_to_study_box_km": distance_km(shared, study_bbox, crs),
        "shared_within_buffer_km2": {
            str(km): within_buffer_km2(shared, study_bbox, km, crs) for km in buffers_km
        },
        "shared_patches": [
            {"km2": area_km2(piece, crs), "bounds": list(piece.bounds)}
            for piece in parts(shared)
        ],
    }


def shared_region(first: list[Box], second: list[Box], padding_deg: float) -> Box:
    """Box around the shared area, padded so edge tiles are not cut off."""
    shared = footprint_geometry(first).intersection(footprint_geometry(second))
    if shared.is_empty:
        raise ValueError("The two acquisitions share no ground")
    west, south, east, north = shared.bounds
    return (
        west - padding_deg,
        south - padding_deg,
        east + padding_deg,
        north + padding_deg,
    )


def shared_tiles(
    first: list[Box],
    second: list[Box],
    tile_size_m: float,
    cells_per_tile: int,
    padding_deg: float,
) -> tuple[list[Box], Box]:
    """Tiles wholly inside both footprints, using the repo's tile rule."""
    region = shared_region(first, second, padding_deg)
    tiles = sources.co_covered_tiles(
        [first, second], region, tile_size_m, cells_per_tile
    )
    return tiles, region
