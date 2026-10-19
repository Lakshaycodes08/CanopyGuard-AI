"""Burned-area raster from fire perimeters, for screening rows only."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray


def alarm_date(value: Any) -> date | None:
    """Alarm date from an ArcGIS epoch-millisecond field, or None if missing."""
    if value is None:
        return None
    return datetime.fromtimestamp(int(value) / 1000.0, tz=UTC).date()


def perimeters_in_window(
    geojson: dict[str, Any], after: date, up_to: date
) -> list[dict[str, Any]]:
    """Perimeters whose alarm date lies in (after, up_to]; undated ones are kept.

    An undated perimeter cannot be shown to precede the survey, so it is
    treated as a possible disturbance rather than silently dropped.
    """
    kept = []
    for feature in geojson["features"]:
        alarm = alarm_date(feature["properties"].get("ALARM_DATE"))
        if alarm is None or after < alarm <= up_to:
            kept.append(feature)
    return kept


def burned_raster(
    perimeters: list[dict[str, Any]],
    grid: tuple[float, float, float, int, int],
    crs: str,
) -> NDArray[np.float32]:
    """0/1 raster on the grid; 1 inside any perimeter."""
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from shapely.geometry import shape
    from shapely.ops import transform

    left, top, step, width, height = grid
    project = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    shapes = [
        (transform(project, shape(f["geometry"])), 1)
        for f in perimeters
        if f["geometry"]
    ]
    if not shapes:
        return np.zeros((int(height), int(width)), dtype=np.float32)
    burned = rasterize(
        shapes,
        (int(height), int(width)),
        fill=0,
        transform=from_origin(left, top, step, step),
        dtype="uint8",
    )
    return burned.astype(np.float32)
