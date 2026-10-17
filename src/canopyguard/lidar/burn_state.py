"""Mark cells that burned between two LiDAR epochs, from fire perimeters."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from canopyguard.config import require_keys

Box = tuple[float, float, float, float]
JsonFetcher = Callable[[str, float], dict[str, Any]]
REQUIRED = ["fire_perimeter_url", "fire_first_year", "fire_last_year", "fire_min_acres"]


def build_query_url(settings: dict[str, Any], region: Box) -> str:
    """Query for perimeters of fires in the epoch gap that meet a region."""
    require_keys(settings, REQUIRED)
    params = {
        "where": (
            f"YEAR_ >= '{settings['fire_first_year']}' "
            f"AND YEAR_ <= '{settings['fire_last_year']}' "
            f"AND GIS_ACRES >= {settings['fire_min_acres']}"
        ),
        "geometry": ",".join(str(value) for value in region),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FIRE_NAME,YEAR_,ALARM_DATE,GIS_ACRES",
        "outSR": "4326",
        "f": "geojson",
    }
    return f"{settings['fire_perimeter_url']}?{urlencode(params)}"


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def fetch_perimeters(
    settings: dict[str, Any],
    region: Box,
    timeout_seconds: float,
    fetch_json: JsonFetcher | None = None,
) -> list[dict[str, Any]]:
    """Fetch fire perimeters; an empty list means no recorded fire in the gap."""
    page = (fetch_json or _fetch_json)(
        build_query_url(settings, region), timeout_seconds
    )
    features = page.get("features")
    if not isinstance(features, list):
        raise ValueError("Fire perimeter response is missing a feature list")
    perimeters = [
        {
            "name": str(feature["properties"].get("FIRE_NAME", "")).strip(),
            "year": int(feature["properties"]["YEAR_"]),
            "acres": float(feature["properties"].get("GIS_ACRES") or 0.0),
            "geometry": shape(feature["geometry"]),
        }
        for feature in features
    ]
    # The service does not order its features, so sort for repeatable reports.
    return sorted(perimeters, key=lambda fire: (fire["year"], fire["name"]))


def burned_mask(
    longitude: np.ndarray, latitude: np.ndarray, perimeters: list[dict[str, Any]]
) -> np.ndarray:
    """True where a point lies inside any fire perimeter."""
    mask = np.zeros(longitude.shape, dtype=bool)
    for perimeter in perimeters:
        geometry: BaseGeometry = perimeter["geometry"]
        mask |= shapely.contains_xy(geometry, longitude, latitude)
    return mask
