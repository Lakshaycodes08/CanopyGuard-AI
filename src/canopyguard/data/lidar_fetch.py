"""Discover airborne LiDAR acquisitions and record a reproducible manifest."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

JsonFetcher = Callable[[str, float], dict[str, Any]]

CATALOG_URL = "https://portal.opentopography.org/API/otCatalog"


def build_catalog_url(
    box: tuple[float, float, float, float],
    product_format: str = "PointCloud",
    include_federated: bool = True,
) -> str:
    """Build a catalogue query for one bounding box."""
    west, south, east, north = box
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")

    params = {
        "productFormat": product_format,
        "minx": west,
        "miny": south,
        "maxx": east,
        "maxy": north,
        "detail": "true",
        "outputFormat": "json",
        "include_federated": str(bool(include_federated)).lower(),
    }
    return f"{CATALOG_URL}?{urlencode(params)}"


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def parse_catalog(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise a catalogue response into flat dataset records."""
    records: list[dict[str, Any]] = []
    for entry in payload.get("Datasets", []):
        dataset = entry.get("Dataset", entry)
        coverage = dataset.get("spatialCoverage", {}).get("geo", {})
        records.append(
            {
                "identifier": _identifier(dataset),
                "name": dataset.get("name"),
                "start": dataset.get("temporalCoverage", "").split("/")[0].strip(),
                "end": dataset.get("temporalCoverage", "").split("/")[-1].strip(),
                "box": _box(coverage),
            }
        )
    return records


def _identifier(dataset: dict[str, Any]) -> str | None:
    identifier = dataset.get("identifier")
    if isinstance(identifier, dict):
        return identifier.get("value")
    return identifier


def _box(coverage: dict[str, Any]) -> tuple[float, float, float, float] | None:
    corners = coverage.get("box")
    if not corners:
        return None
    parts = [float(value) for value in str(corners).split()]
    if len(parts) != 4:
        return None
    south, west, north, east = parts
    return (west, south, east, north)


def present_identifiers(records: list[dict[str, Any]]) -> set[str]:
    """Identifiers returned for a probe box."""
    return {record["identifier"] for record in records if record["identifier"]}


def probe_coverage(
    boxes: list[tuple[float, float, float, float]],
    identifier: str,
    timeout_seconds: float = 60.0,
    fetch_json: JsonFetcher | None = None,
) -> list[bool]:
    """Report whether one dataset is returned for each probe box.

    A published acquisition bounding box is the hull of its work units. Probing
    is what establishes where the acquisition is actually present.
    """
    fetch = fetch_json or _fetch_json
    return [
        identifier in present_identifiers(parse_catalog(fetch(url, timeout_seconds)))
        for url in (build_catalog_url(box) for box in boxes)
    ]


def build_tile_manifest(
    tiles: list[dict[str, Any]], epoch: str, source_url: str
) -> dict[str, Any]:
    """Record the tiles an epoch needs, sorted and deduplicated by URL."""
    required = ("url", "bytes", "sha256", "box")
    selected: dict[str, dict[str, Any]] = {}
    for tile in tiles:
        missing = [key for key in required if key not in tile]
        if missing:
            raise ValueError("Tile is missing fields: " + ", ".join(missing))
        selected[tile["url"]] = {key: tile[key] for key in required}

    records = sorted(selected.values(), key=lambda tile: tile["url"])
    return {
        "contract_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "epoch": epoch,
        "source": source_url,
        "tile_count": len(records),
        "total_bytes": sum(int(tile["bytes"]) for tile in records),
        "tiles": records,
    }
