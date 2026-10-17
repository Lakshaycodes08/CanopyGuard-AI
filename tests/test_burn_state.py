from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest
from shapely.geometry import box

from canopyguard.lidar import burn_state

SETTINGS = {
    "fire_perimeter_url": "https://example.test/query",
    "fire_first_year": 2018,
    "fire_last_year": 2023,
    "fire_min_acres": 100,
}


def test_query_limits_years_size_and_region() -> None:
    url = burn_state.build_query_url(SETTINGS, (-122.3, 38.7, -122.1, 39.0))
    query = parse_qs(urlsplit(url).query)

    assert query["where"] == [
        "YEAR_ >= '2018' AND YEAR_ <= '2023' AND GIS_ACRES >= 100"
    ]
    assert query["geometry"] == ["-122.3,38.7,-122.1,39.0"]


def test_fetch_perimeters_parses_name_year_and_geometry() -> None:
    page = {
        "features": [
            {
                "properties": {"FIRE_NAME": "TEST ", "YEAR_": "2020", "GIS_ACRES": 500},
                "geometry": box(0, 0, 1, 1).__geo_interface__,
            }
        ]
    }

    (fire,) = burn_state.fetch_perimeters(
        SETTINGS, (0, 0, 1, 1), 5, lambda url, timeout: page
    )

    assert (fire["name"], fire["year"], fire["acres"]) == ("TEST", 2020, 500.0)
    assert fire["geometry"].area == pytest.approx(1.0)


def test_fetch_perimeters_rejects_a_malformed_response() -> None:
    with pytest.raises(ValueError, match="feature list"):
        burn_state.fetch_perimeters(SETTINGS, (0, 0, 1, 1), 5, lambda url, timeout: {})


def test_burned_mask_marks_points_inside_any_perimeter() -> None:
    perimeters = [{"geometry": box(0, 0, 1, 1)}, {"geometry": box(5, 5, 6, 6)}]
    lon = np.array([0.5, 5.5, 3.0])
    lat = np.array([0.5, 5.5, 3.0])

    assert burn_state.burned_mask(lon, lat, perimeters).tolist() == [True, True, False]
    assert not burn_state.burned_mask(lon, lat, []).any()


def test_perimeters_come_back_sorted_by_year_then_name() -> None:
    def feature(name: str, year: str) -> dict:
        return {
            "properties": {"FIRE_NAME": name, "YEAR_": year, "GIS_ACRES": 200},
            "geometry": box(0, 0, 1, 1).__geo_interface__,
        }

    page = {
        "features": [feature("B", "2020"), feature("A", "2020"), feature("C", "2018")]
    }

    fires = burn_state.fetch_perimeters(
        SETTINGS, (0, 0, 1, 1), 5, lambda url, timeout: page
    )

    assert [(fire["year"], fire["name"]) for fire in fires] == [
        (2018, "C"),
        (2020, "A"),
        (2020, "B"),
    ]
