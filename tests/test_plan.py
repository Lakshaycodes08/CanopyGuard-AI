from __future__ import annotations

import pytest

from canopyguard.config import load_config
from canopyguard.lidar.ept import to_web_mercator
from canopyguard.lidar.plan import (
    calibration_plan,
    calibration_tiles,
    dispersion_grid_side,
    noise_floor_projects,
    search_box,
)
from canopyguard.lidar.sources import parse_manifest


def delivery_grid(west, south, east, north, step=0.0116):
    """A work unit as a grid of delivery tiles of about 1290 m."""
    entries = []
    latitude = south
    while latitude < north - 1e-12:
        longitude = west
        while longitude < east - 1e-12:
            min_x, min_y = to_web_mercator(longitude, latitude)
            max_x, max_y = to_web_mercator(longitude + step, latitude + step)
            entries.append(
                {"bounds": [min_x, min_y, 0.0, max_x, max_y, 100.0], "points": 10**6}
            )
            longitude += step
        latitude += step
    return parse_manifest(entries)


@pytest.fixture
def lidar_config():
    return load_config("configs/lidar.yaml")


@pytest.fixture
def footprints():
    """Two work units overlapping over a band several tiles wide."""
    return {
        "2022": delivery_grid(-123.00, 38.50, -122.80, 38.70),
        "2023": delivery_grid(-122.88, 38.50, -122.60, 38.70),
    }


def test_search_box_comes_from_the_config(lidar_config):
    assert search_box(lidar_config) == (-123.40, 38.10, -122.30, 38.90)


def test_search_box_must_be_set(lidar_config):
    lidar_config["noise_floor"]["search_box"] = None
    with pytest.raises(ValueError, match="search_box"):
        search_box(lidar_config)


def test_noise_floor_projects_are_the_two_recent_epochs(lidar_config):
    projects = noise_floor_projects(lidar_config)
    assert set(projects) == {"2022", "2023"}
    assert projects["2023"] == "CA_NorthCoastRanges_2_B23"


def test_missing_dataset_is_reported(lidar_config):
    lidar_config["noise_floor"]["epoch_pair"] = ["2022", "1999"]
    with pytest.raises(ValueError, match="No dataset for epochs: 1999"):
        noise_floor_projects(lidar_config)


def test_calibration_tiles_need_a_footprint_per_epoch(lidar_config, footprints):
    with pytest.raises(ValueError, match="No footprint for epochs: 2023"):
        calibration_tiles(lidar_config, {"2022": footprints["2022"]})


def test_calibration_tiles_lie_inside_both_work_units(lidar_config, footprints):
    tiles = calibration_tiles(lidar_config, footprints)
    assert tiles
    for west, _, east, _ in tiles:
        assert west >= -122.8801
        assert east <= -122.79


def test_a_tile_wider_than_the_overlap_yields_nothing(lidar_config, footprints):
    """The work units in the study area abut rather than overlap, and no
    square of the original 1000 m tile size fits inside the seam."""
    lidar_config["tiers"]["sample_tile_size_m"] = 20000
    assert calibration_tiles(lidar_config, footprints) == []


def test_plan_refuses_to_run_without_co_coverage(lidar_config, footprints):
    lidar_config["tiers"]["sample_tile_size_m"] = 20000
    with pytest.raises(ValueError, match="covered in full"):
        calibration_plan(lidar_config, 10, footprints)


def test_plan_draws_the_requested_tile_count(lidar_config, footprints):
    plan = calibration_plan(lidar_config, 40, footprints)
    assert plan["tile_count"] == 40
    assert plan["candidate_tiles"] >= 40
    assert plan["sample_area_km2"] == pytest.approx(40 * 0.0625, rel=0.05)


def test_plan_never_draws_more_than_the_co_coverage_allows(
    lidar_config, footprints
):
    plan = calibration_plan(lidar_config, 10**6, footprints)
    assert plan["tile_count"] == plan["candidate_tiles"]


def test_plan_carries_a_reader_per_epoch_per_tile(lidar_config, footprints):
    plan = calibration_plan(lidar_config, 25, footprints)
    for tile in plan["tiles"]:
        assert set(tile["readers"]) == {"2022", "2023"}
        for reader in tile["readers"].values():
            assert reader["type"] == "readers.ept"
            assert reader["bounds"].startswith("([")


def test_plan_carries_one_raster_grid_per_tile(lidar_config, footprints):
    plan = calibration_plan(lidar_config, 10, footprints)
    for tile in plan["tiles"]:
        grid = tile["grid"]
        assert grid["resolution_m"] == 1.0
        assert 230 <= grid["width"] <= 270
        assert 230 <= grid["height"] <= 270


def test_plan_uses_the_sparsest_epoch_for_the_sampling_radius(
    lidar_config, footprints
):
    plan = calibration_plan(lidar_config, 25, footprints)
    assert plan["sample_radius_m"] == pytest.approx(0.2699, abs=1e-3)


def test_plan_spreads_tiles_across_the_co_coverage(lidar_config, footprints):
    """Sampling is stratified on a coarse grid, so tiles cannot clump."""
    plan = calibration_plan(lidar_config, 25, footprints)
    latitudes = [tile["box"][1] for tile in plan["tiles"]]
    _, south, _, north = plan["coverage_box"]
    assert max(latitudes) - min(latitudes) > 0.5 * (north - south)


def test_plan_is_deterministic(lidar_config, footprints):
    first = calibration_plan(lidar_config, 20, footprints, seed=7)
    second = calibration_plan(lidar_config, 20, footprints, seed=7)
    assert [tile["box"] for tile in first["tiles"]] == [
        tile["box"] for tile in second["tiles"]
    ]


def test_dispersion_grid_never_outnumbers_the_sample():
    for count in (1, 4, 9, 20, 25, 40, 100):
        side = dispersion_grid_side(count)
        assert side * side <= count
    with pytest.raises(ValueError, match="must be positive"):
        dispersion_grid_side(0)


@pytest.mark.parametrize("count", [1, 5, 16, 40, 64])
def test_plan_succeeds_across_sample_sizes(lidar_config, footprints, count):
    assert calibration_plan(lidar_config, count, footprints)["tile_count"] == count
