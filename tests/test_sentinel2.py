from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from canopyguard.data.sentinel2 import (
    build_manifest,
    build_search_url,
    fetch_catalogue_items,
)


@pytest.fixture
def study_config() -> dict:
    return {
        "study_area": {"bbox": {"west": -3, "south": 1, "east": -2, "north": 2}},
        "dates": {"start": "2020-01-01", "end": "2020-12-31"},
    }


@pytest.fixture
def ingestion_config() -> dict:
    return {
        "sentinel2": {
            "stac_url": "https://example.test/v1",
            "collection": "sentinel-2-l2a",
            "tile_code": "MGRS-10SEH",
            "max_tile_cloud_percent": 20,
            "page_size": 100,
            "assets": ["B04_10m", "SCL_20m"],
            "scl_excluded_classes": [0, 1, 3, 8, 9, 10, 11],
        }
    }


def test_build_search_url_uses_bbox_dates_and_cloud_limit(
    study_config: dict, ingestion_config: dict
) -> None:
    url = build_search_url(study_config, ingestion_config)
    query = parse_qs(urlsplit(url).query)

    assert query["bbox"] == ["-3,1,-2,2"]
    assert query["datetime"] == ["2020-01-01T00:00:00Z/2020-12-31T23:59:59Z"]
    assert query["filter"] == ["eo:cloud_cover <= 20 AND grid:code = 'MGRS-10SEH'"]


def test_fetch_catalogue_items_follows_get_pages() -> None:
    pages = {
        "https://example.test/search": {
            "features": [{"id": "first"}],
            "links": [{"rel": "next", "href": "https://example.test/page-2"}],
        },
        "https://example.test/page-2": {"features": [{"id": "second"}]},
    }

    items = fetch_catalogue_items(
        "https://example.test/search", 10, lambda url, timeout: pages[url]
    )

    assert [item["id"] for item in items] == ["first", "second"]


def test_fetch_catalogue_items_rejects_changed_origin() -> None:
    page = {
        "features": [],
        "links": [{"rel": "next", "href": "https://other.test/page-2"}],
    }

    with pytest.raises(ValueError, match="changed origin"):
        fetch_catalogue_items(
            "https://example.test/search", 10, lambda url, timeout: page
        )


def test_build_manifest_filters_tile_cloud_and_duplicate(
    ingestion_config: dict,
) -> None:
    good = _item("b", "2020-02-01T00:00:00Z", "MGRS-10SEH", 5)
    earlier = _item("a", "2020-01-01T00:00:00Z", "MGRS-10SEH", 10)
    wrong_tile = _item("c", "2020-01-01T00:00:00Z", "MGRS-10SEJ", 1)
    too_cloudy = _item("d", "2020-01-01T00:00:00Z", "MGRS-10SEH", 21)

    manifest = build_manifest(
        [good, earlier, wrong_tile, too_cloudy, good],
        ingestion_config,
        generated_at="2026-09-15T00:00:00+00:00",
    )

    assert manifest["item_count"] == 2
    assert [item["id"] for item in manifest["items"]] == ["a", "b"]
    assert set(manifest["items"][0]["assets"]) == {"B04_10m", "SCL_20m"}


def test_build_manifest_rejects_missing_asset(ingestion_config: dict) -> None:
    item = _item("a", "2020-01-01T00:00:00Z", "MGRS-10SEH", 1)
    del item["assets"]["SCL_20m"]

    with pytest.raises(ValueError, match="missing assets"):
        build_manifest([item], ingestion_config)


def _item(item_id: str, acquired: str, tile: str, cloud: float) -> dict:
    return {
        "id": item_id,
        "properties": {
            "datetime": acquired,
            "grid:code": tile,
            "eo:cloud_cover": cloud,
        },
        "assets": {
            "B04_10m": {"href": f"https://example.test/{item_id}/B04.tif"},
            "SCL_20m": {"href": f"https://example.test/{item_id}/SCL.tif"},
        },
    }
