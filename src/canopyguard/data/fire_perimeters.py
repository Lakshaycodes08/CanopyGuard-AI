"""Fetch study-box ArcGIS fire perimeters and CEC lines as raw GeoJSON."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import requests
from pyproj import Transformer
from shapely import points
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree

from canopyguard.io import ensure_parent


def _request(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=120)
    response.raise_for_status()
    document = response.json()
    if "error" in document:
        raise ValueError(f"ArcGIS query failed: {document['error']}")
    return document


def fetch_study_features(url: str, bbox: dict, where: str, path: Path) -> int:
    """Download only features intersecting the configured study box."""
    if path.exists():
        return len(json.loads(path.read_text(encoding="utf-8"))["features"])
    envelope = ",".join(str(bbox[key]) for key in ("west", "south", "east", "north"))
    params = {
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "where": where,
        "outFields": "*",
        "f": "geojson",
    }
    count = _request(url, {**params, "f": "json", "returnCountOnly": "true"})["count"]
    if count > 2000:
        raise ValueError("Study-box source exceeds one ArcGIS page")
    document = _request(url, params)
    features = document.get("features", [])
    if len(features) != count:
        raise ValueError(f"ArcGIS count changed: expected {count}, got {len(features)}")
    ensure_parent(path).write_text(
        json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return count


def projected_features(path: Path) -> list[tuple[object, dict]]:
    project = Transformer.from_crs(4326, 6339, always_xy=True).transform
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        (transform(project, shape(item["geometry"])), item["properties"])
        for item in document["features"]
        if item.get("geometry")
    ]


def point_hits(
    x: np.ndarray,
    y: np.ndarray,
    geometries: list,
    chunk_size: int,
) -> np.ndarray:
    """Mark points intersecting any polygon or buffered line."""
    output = np.zeros(len(x), dtype=bool)
    if not geometries:
        return output
    tree = STRtree(geometries)
    for start in range(0, len(x), chunk_size):
        stop = min(start + chunk_size, len(x))
        matches = tree.query(
            points(x[start:stop], y[start:stop]), predicate="intersects"
        )
        output[start + matches[0]] = True
    return output


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
