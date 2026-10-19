"""Approximate transmission-line geometry from the county copy of the CEC layer."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_lines(
    bbox_wgs84: tuple[float, float, float, float], config: dict[str, Any]
) -> dict[str, Any]:
    """GeoJSON line features intersecting the box, in EPSG:4326."""
    west, south, east, north = bbox_wgs84
    params = {
        "where": "1=1",
        "geometry": f"{west},{south},{east},{north}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "outSR": 4326,
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }
    url = f"{config['url']}?{urlencode(params)}"
    with urlopen(url, timeout=config["request_timeout_seconds"]) as response:  # noqa: S310
        return json.load(response)
