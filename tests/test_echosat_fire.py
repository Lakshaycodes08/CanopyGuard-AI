from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely.geometry import box as shapely_box

from canopyguard.data import echosat, echosat_fire

NODATA = -9999
BBOX = (-122.9, 38.4, -122.8, 38.5)
YEARS = [2018, 2019, 2020]


@pytest.fixture
def fire() -> dict:
    return {
        "perimeter_url": "https://example.test/query",
        "fire_name": "TEST",
        "fire_year": 2018,
    }


@pytest.fixture
def source(fire: dict) -> dict:
    return {
        "band_years": YEARS,
        "nodata_value": NODATA,
        "height_scale_to_m": 0.01,
        "abrupt_change_m": 5,
        "fire_check": fire,
    }


@pytest.fixture
def pixel_box() -> echosat.BoxRead:
    """A 4x4 lon/lat grid. Left half loses 9 m between bands 1 and 2."""
    data = np.full((3, 4, 4), 1000, dtype="int16")
    data[1, :, :2] = 100
    data[2, :, :2] = 100
    transform = from_origin(-122.9, 38.5, 0.025, 0.025)
    inside = np.ones((4, 4), dtype=bool)
    return echosat.BoxRead(
        data, Window(0, 0, 4, 4), transform, inside, True, "EPSG:4326"
    )


def test_build_perimeter_url_filters_name_year_and_box(fire: dict) -> None:
    query = parse_qs(urlsplit(echosat_fire.build_perimeter_url(fire, BBOX)).query)

    assert query["where"] == ["FIRE_NAME='TEST' AND YEAR_='2018'"]
    assert query["geometry"] == ["-122.9,38.4,-122.8,38.5"]
    assert query["f"] == ["geojson"]


def test_fetch_fire_perimeter_merges_polygons(fire: dict) -> None:
    def fetch(url: str, timeout: float) -> dict:
        geometry = shapely_box(0, 0, 1, 1).__geo_interface__
        return {"features": [{"geometry": geometry}, {"geometry": geometry}]}

    perimeter = echosat_fire.fetch_fire_perimeter(fire, BBOX, 5, fetch)

    assert perimeter.area == pytest.approx(1.0)


def test_fetch_fire_perimeter_rejects_empty_result(fire: dict) -> None:
    with pytest.raises(ValueError, match="No perimeter found"):
        echosat_fire.fetch_fire_perimeter(
            fire, BBOX, 5, lambda url, timeout: {"features": []}
        )


def test_count_drops_in_perimeter_splits_inside_and_outside(
    pixel_box: echosat.BoxRead,
) -> None:
    left_half = shapely_box(-122.9, 38.4, -122.85, 38.5)

    counts = echosat_fire.count_drops_in_perimeter(
        pixel_box, left_half, YEARS, NODATA, 5, 0.01
    )

    first, second = counts["steps"]
    assert counts["perimeter_share_of_box"] == pytest.approx(0.5)
    assert (first["drop_pixels"], first["drop_pixels_in_perimeter"]) == (8, 8)
    assert (second["drop_pixels"], second["drop_pixels_in_perimeter"]) == (0, 0)


def test_fire_check_flags_peak_step_against_fire_year(
    pixel_box: echosat.BoxRead, source: dict
) -> None:
    left_half = shapely_box(-122.9, 38.4, -122.85, 38.5)

    forward = echosat_fire.fire_check(pixel_box, left_half, source)
    late_fire = {**source, "fire_check": {**source["fire_check"], "fire_year": 2019}}
    mismatch = echosat_fire.fire_check(pixel_box, left_half, late_fire)

    assert forward["peak_step"] == [2018, 2019]
    assert forward["peak_matches_expected"] is True
    assert mismatch["peak_matches_expected"] is False
