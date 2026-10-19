from __future__ import annotations

import json

import numpy as np
import pytest

from canopyguard.config import load_config
from canopyguard.lidar import pair_coverage, pair_overlap
from canopyguard.lidar.ept import to_web_mercator

STUDY = (-122.90, 38.475, -122.74, 38.82)
EARLIER = [(-122.30, 38.70, -122.20, 38.80)]
LATER = [(-122.25, 38.75, -122.10, 38.90)]


@pytest.fixture
def lidar_config() -> dict:
    return load_config("configs/lidar.yaml")


def footprint(name: str):
    return EARLIER if name == "CA_NoCAL_Wildfires_TL_QL2_2018" else LATER


def fake_fetch(url: str) -> bytes:
    x0, y0 = to_web_mercator(-122.4, 38.6)
    x1, y1 = to_web_mercator(-122.0, 39.0)
    if url.endswith("ept.json"):
        return json.dumps({"bounds": [x0, y0, -10, x1, y1, 10]}).encode()
    if url.endswith("0-0-0-0.json"):
        return json.dumps({"0-0-0-0": 1250}).encode()
    return url.encode()


def make_reader(lidar_config: dict):
    tiles, _ = pair_overlap.shared_tiles(EARLIER, LATER, 250, 5, 0.005)
    west, south, east, north = tiles[0]
    steps = (np.arange(25) + 0.5) / 25
    lon = np.tile(west + (east - west) * steps, 25)
    lat = np.repeat(south + (north - south) * steps, 25)
    x, y = zip(
        *(to_web_mercator(a, b) for a, b in zip(lon, lat, strict=True)), strict=True
    )

    def read(raw: bytes) -> dict[str, np.ndarray]:
        top = 110.0 if b"2018" in raw else 112.0
        count = len(x)
        return {
            "x": np.array(list(x) * 2),
            "y": np.array(list(y) * 2),
            "z": np.array([100.0] * count + [top] * count),
            "classification": np.array([2] * count + [1] * count, dtype=np.uint8),
            "flags": np.zeros(2 * count, dtype=np.uint8),
        }

    return read


def test_run_reports_overlap_location_and_usable_canopy(lidar_config: dict) -> None:
    report, stats = pair_coverage.run(
        lidar_config,
        STUDY,
        footprint=footprint,
        fetch=fake_fetch,
        read_points=make_reader(lidar_config),
        fetch_json=lambda url, timeout: {"features": []},
    )

    answer = report["answer"]
    assert report["overlap"]["shared_km2"] == pytest.approx(24.1, rel=0.05)
    assert answer["shared_in_study_box_km2"] == 0.0
    assert answer["distance_to_study_box_km"] == pytest.approx(42.0, rel=0.05)
    assert answer["valid_both_tiles"] == 1
    assert answer["usable_canopy_km2"] == pytest.approx(625 * 1e-4)
    assert answer["usable_canopy_meets_minimum"] is False
    assert report["pair"]["lidar_height_change_m_on_undisturbed"][
        "median"
    ] == pytest.approx(2.0)
    assert set(stats) == {"2018", "2023"}


def test_a_fire_perimeter_removes_burned_canopy(lidar_config: dict) -> None:
    tiles, _ = pair_overlap.shared_tiles(EARLIER, LATER, 250, 5, 0.005)
    west, south, east, north = tiles[0]
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    fire = {
        "features": [
            {
                "properties": {"FIRE_NAME": "TEST", "YEAR_": "2020", "GIS_ACRES": 900},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ]
    }

    report, _ = pair_coverage.run(
        lidar_config,
        STUDY,
        footprint=footprint,
        fetch=fake_fetch,
        read_points=make_reader(lidar_config),
        fetch_json=lambda url, timeout: fire,
    )

    assert report["answer"]["usable_canopy_km2"] == 0.0
    assert report["pair"]["area_km2"]["burned_canopy"] == pytest.approx(625 * 1e-4)
    assert report["fires_in_gap"][0]["name"] == "TEST"


def test_disjoint_acquisitions_are_reported(lidar_config: dict) -> None:
    def far(name: str):
        return [(0.0, 0.0, 0.1, 0.1)] if "2018" in name else [(5.0, 5.0, 5.1, 5.1)]

    with pytest.raises(ValueError, match="share no ground"):
        pair_coverage.run(lidar_config, STUDY, footprint=far, fetch=fake_fetch)


def test_overlap_too_small_for_a_tile_gives_a_zero_answer(lidar_config: dict) -> None:
    def sliver(name: str):
        if "2018" in name:
            return [(-122.2, 38.7, -122.1990, 38.8)]
        return [(-122.1995, 38.7, -122.1, 38.8)]

    report, stats = pair_coverage.run(
        lidar_config, STUDY, footprint=sliver, fetch=fake_fetch
    )

    assert report["answer"]["shared_tiles"] == 0
    assert report["answer"]["usable_canopy_km2"] == 0.0
    assert stats == {}


def test_missing_section_is_reported(lidar_config: dict) -> None:
    del lidar_config["pair_coverage"]

    with pytest.raises(ValueError, match="no pair_coverage section"):
        pair_coverage.settings(lidar_config)


def test_epoch_resources_resolve_both_epochs(lidar_config: dict) -> None:
    resources = pair_coverage.epoch_resources(lidar_config)

    assert resources == {
        "2018": ["CA_NoCAL_Wildfires_TL_QL2_2018"],
        "2023": ["CA_NorthCoastRanges_2_B23"],
    }


def test_map_is_written_for_a_run(lidar_config: dict, tmp_path) -> None:
    from canopyguard.viz.pair_coverage import save_map

    report, _ = pair_coverage.run(
        lidar_config,
        STUDY,
        footprint=footprint,
        fetch=fake_fetch,
        read_points=make_reader(lidar_config),
        fetch_json=lambda url, timeout: {"features": []},
    )

    output = save_map(report, STUDY, tmp_path / "out" / "map.png", dpi=40)

    assert output.stat().st_size > 0


def test_sensitivity_moves_one_threshold_at_a_time(lidar_config: dict) -> None:
    report, _ = pair_coverage.run(
        lidar_config,
        STUDY,
        footprint=footprint,
        fetch=fake_fetch,
        read_points=make_reader(lidar_config),
        fetch_json=lambda url, timeout: {"features": []},
    )

    rows = report["sensitivity"]
    by_canopy = {
        row["value"]: row["usable_canopy_km2"]
        for row in rows
        if row["parameter"] == "canopy_min_m"
    }
    assert {row["parameter"] for row in rows} == set(
        lidar_config["pair_coverage"]["sensitivity"]
    )
    assert by_canopy[2.0] == pytest.approx(625 * 1e-4)
    assert by_canopy[5.0] == pytest.approx(625 * 1e-4)  # fake canopy is 10 m and 12 m
    assert by_canopy[10.0] == pytest.approx(625 * 1e-4)
