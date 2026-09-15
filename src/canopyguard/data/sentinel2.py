"""Build a reproducible Sentinel-2 scene manifest from the Copernicus STAC."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

from canopyguard.config import require_keys
from canopyguard.io import data_path, ensure_parent

JsonFetcher = Callable[[str, float], dict[str, Any]]


def build_search_url(
    study_config: dict[str, Any], ingestion_config: dict[str, Any]
) -> str:
    """Build the configured Copernicus STAC search URL."""
    require_keys(study_config, ["study_area", "dates"])
    require_keys(ingestion_config, ["sentinel2"])
    source = ingestion_config["sentinel2"]
    require_keys(
        source,
        [
            "stac_url",
            "collection",
            "tile_code",
            "max_tile_cloud_percent",
            "page_size",
        ],
    )

    bbox = study_config["study_area"]["bbox"]
    dates = study_config["dates"]
    coordinates = [bbox[key] for key in ("west", "south", "east", "north")]
    if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
        msg = "Study-area bbox must satisfy west < east and south < north"
        raise ValueError(msg)

    params = {
        "collections": source["collection"],
        "datetime": f"{dates['start']}T00:00:00Z/{dates['end']}T23:59:59Z",
        "bbox": ",".join(str(value) for value in coordinates),
        "filter": (
            f"eo:cloud_cover <= {source['max_tile_cloud_percent']} "
            f"AND grid:code = '{source['tile_code']}'"
        ),
        "limit": source["page_size"],
    }
    return f"{source['stac_url'].rstrip('/')}/search?{urlencode(params)}"


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def fetch_catalogue_items(
    search_url: str,
    timeout_seconds: float,
    fetch_json: JsonFetcher | None = None,
) -> list[dict[str, Any]]:
    """Fetch all GET pages while keeping pagination on the configured host."""
    fetch = fetch_json or _fetch_json
    expected_origin = urlsplit(search_url)[:2]
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    next_url: str | None = search_url

    while next_url:
        if next_url in seen_urls:
            raise ValueError("STAC pagination repeated a URL")
        if urlsplit(next_url)[:2] != expected_origin:
            raise ValueError("STAC pagination changed origin")
        seen_urls.add(next_url)

        page = fetch(next_url, timeout_seconds)
        features = page.get("features")
        if not isinstance(features, list):
            raise ValueError("STAC response is missing a feature list")
        items.extend(features)
        next_url = _next_get_link(page)

    return items


def _next_get_link(page: dict[str, Any]) -> str | None:
    for link in page.get("links", []):
        if link.get("rel") != "next":
            continue
        if link.get("method", "GET").upper() != "GET":
            raise ValueError("STAC pagination requires an unsupported method")
        return link.get("href")
    return None


def build_manifest(
    items: list[dict[str, Any]],
    ingestion_config: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Select, validate, deduplicate, and sort items for the configured tile."""
    source = ingestion_config["sentinel2"]
    required_assets = source["assets"]
    selected: dict[str, dict[str, Any]] = {}

    for item in items:
        properties = item.get("properties", {})
        if properties.get("grid:code") != source["tile_code"]:
            continue
        cloud_cover = properties.get("eo:cloud_cover")
        if cloud_cover is None or cloud_cover > source["max_tile_cloud_percent"]:
            continue
        selected[item["id"]] = _manifest_item(item, required_assets)

    records = sorted(selected.values(), key=lambda item: (item["datetime"], item["id"]))
    timestamp = generated_at or datetime.now(UTC).isoformat()
    return {
        "contract_version": 1,
        "generated_at": timestamp,
        "source": source["stac_url"],
        "collection": source["collection"],
        "tile_code": source["tile_code"],
        "item_count": len(records),
        "assets": required_assets,
        "scl_excluded_classes": source["scl_excluded_classes"],
        "items": records,
    }


def _manifest_item(item: dict[str, Any], required_assets: list[str]) -> dict[str, Any]:
    assets = item.get("assets", {})
    missing = [name for name in required_assets if name not in assets]
    if missing:
        msg = f"STAC item {item.get('id')} is missing assets: {', '.join(missing)}"
        raise ValueError(msg)
    return {
        "id": item["id"],
        "datetime": item["properties"]["datetime"],
        "cloud_cover": item["properties"]["eo:cloud_cover"],
        "assets": {name: assets[name]["href"] for name in required_assets},
    }


def write_manifest(
    manifest: dict[str, Any], relative_path: str, root: str | Path | None = None
) -> Path:
    """Write a manifest inside data/ and return its resolved path."""
    output = ensure_parent(data_path(relative_path, root=root))
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output
