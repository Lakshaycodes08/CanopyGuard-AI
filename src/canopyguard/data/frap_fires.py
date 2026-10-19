"""CAL FIRE FRAP fire perimeters for a box, in EPSG:4326."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_perimeters(
    bbox_wgs84: tuple[float, float, float, float], config: dict[str, Any]
) -> dict[str, Any]:
    """GeoJSON perimeters from `min_year` on that intersect the box."""
    west, south, east, north = bbox_wgs84
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "where": f"YEAR_>={int(config['min_year'])}",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "YEAR_,FIRE_NAME,ALARM_DATE,CONT_DATE",
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
            return {"type": "FeatureCollection", "features": features}
        offset += len(page)
