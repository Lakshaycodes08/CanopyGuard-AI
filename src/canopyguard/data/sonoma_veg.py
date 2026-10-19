"""Sonoma County 2013 vegetation map classes rasterised onto the Landsat grid.

Only class-name fields are requested. The layer's LiDAR height, cover and
biomass columns are airborne-survey products and are never read.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from numpy.typing import NDArray


def fetch_class_polygons(
    bbox_wgs84: tuple[float, float, float, float], crs: str, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """GeoJSON features (class names and geometry only) in the grid CRS."""
    west, south, east, north = bbox_wgs84
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": crs.split(":")[1],
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": ",".join(config["fields"]),
            "returnGeometry": "true",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": config["page_size"],
            "f": "geojson",
        }
        url = f"{config['url']}?{urlencode(params)}"
        with urlopen(url, timeout=config["request_timeout_seconds"]) as response:  # noqa: S310
            page = json.load(response)["features"]
        features.extend(page)
        if len(page) < int(config["page_size"]):
            return features
        offset += len(page)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def class_rasters(
    features: list[dict[str, Any]],
    grid: tuple[float, float, float, int, int],
    config: dict[str, Any],
) -> dict[str, NDArray[np.float32]]:
    """0/1 rasters per map class and per forest lifeform; NaN outside the map."""
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    left, top, step, width, height = grid
    transform = from_origin(left, top, step, step)
    out: dict[str, NDArray[np.float32]] = {}
    for field, prefix in (("MAP_CLASS", "veg"), ("LF_FOREST", "lf")):
        names = sorted({f["properties"][field] or "unmapped" for f in features})
        code = {name: i + 1 for i, name in enumerate(names)}
        shapes = [
            (f["geometry"], code[f["properties"][field] or "unmapped"])
            for f in features
            if f["geometry"]
        ]
        codes = rasterize(
            shapes,
            (int(height), int(width)),
            fill=0,
            transform=transform,
            dtype="int32",
        )
        outside = codes == 0
        for name, value in code.items():
            hits = codes == value
            if hits.sum() < int(config["min_pixels_per_class"]):
                continue
            layer = hits.astype(np.float32)
            layer[outside] = np.nan
            out[f"{prefix}_{slug(name)}"] = layer
    return out
