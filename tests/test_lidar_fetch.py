from __future__ import annotations

import pytest

from canopyguard.data.lidar_fetch import (
    build_catalog_url,
    build_tile_manifest,
    parse_catalog,
    present_identifiers,
    probe_coverage,
)

STUDY = (-122.90, 38.475, -122.74, 38.82)


def catalog_payload(*identifiers):
    return {
        "Datasets": [
            {
                "Dataset": {
                    "name": f"dataset {value}",
                    "identifier": {"value": value},
                    "temporalCoverage": "2022-09-13 / 2022-11-11",
                    "spatialCoverage": {"geo": {"box": "38.09 -123.53 38.93 -122.35"}},
                }
            }
            for value in identifiers
        ]
    }


def test_catalog_url_carries_the_box():
    url = build_catalog_url(STUDY)
    assert "minx=-122.9" in url
    assert "maxy=38.82" in url
    assert "productFormat=PointCloud" in url


def test_catalog_url_rejects_an_inverted_box():
    with pytest.raises(ValueError, match="west < east"):
        build_catalog_url((1.0, 0.0, 0.0, 1.0))


def test_parse_catalog_flattens_records_and_reorders_the_box():
    record = parse_catalog(catalog_payload("CA_NorthernCA_1_B22"))[0]
    assert record["identifier"] == "CA_NorthernCA_1_B22"
    assert record["start"] == "2022-09-13"
    assert record["end"] == "2022-11-11"
    assert record["box"] == (-123.53, 38.09, -122.35, 38.93)


def test_parse_catalog_tolerates_an_empty_response():
    assert parse_catalog({}) == []


def test_present_identifiers_collects_the_returned_datasets():
    records = parse_catalog(catalog_payload("A", "B"))
    assert present_identifiers(records) == {"A", "B"}


def test_probe_coverage_reports_presence_per_box():
    """The 2023 epoch returns only for the northern probe."""
    north = (-122.90, 38.78, -122.74, 38.82)
    south = (-122.90, 38.48, -122.74, 38.55)

    def fake_fetch(url, timeout):
        return catalog_payload("B23") if "miny=38.78" in url else catalog_payload("B22")

    assert probe_coverage([north, south], "B23", fetch_json=fake_fetch) == [True, False]


def test_tile_manifest_deduplicates_and_sorts():
    tiles = [
        {"url": "https://x/b.laz", "bytes": 20, "sha256": "b", "box": STUDY},
        {"url": "https://x/a.laz", "bytes": 10, "sha256": "a", "box": STUDY},
        {"url": "https://x/a.laz", "bytes": 10, "sha256": "a", "box": STUDY},
    ]
    manifest = build_tile_manifest(tiles, "2022", "https://source")
    assert manifest["tile_count"] == 2
    assert manifest["total_bytes"] == 30
    assert [tile["url"] for tile in manifest["tiles"]] == [
        "https://x/a.laz",
        "https://x/b.laz",
    ]


def test_tile_manifest_names_missing_fields():
    with pytest.raises(ValueError, match="missing fields"):
        build_tile_manifest([{"url": "https://x/a.laz"}], "2022", "https://source")
