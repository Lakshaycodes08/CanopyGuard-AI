from __future__ import annotations

import pytest

from canopyguard.config import load_config
from canopyguard.lidar.plan import (
    calibration_box,
    calibration_plan,
    dispersion_grid_side,
    noise_floor_projects,
)


@pytest.fixture
def lidar_config():
    return load_config("configs/lidar.yaml")


def test_calibration_box_comes_from_the_verified_intersection(lidar_config):
    box = calibration_box(lidar_config)
    assert box == (-123.39, 38.79, -122.36, 38.93)


def test_calibration_box_requires_verification(lidar_config):
    lidar_config["noise_floor"]["verified_intersection"] = None
    with pytest.raises(ValueError, match="verified_intersection"):
        calibration_box(lidar_config)


def test_noise_floor_projects_are_the_two_recent_epochs(lidar_config):
    projects = noise_floor_projects(lidar_config)
    assert set(projects) == {"2022", "2023"}
    assert projects["2023"] == "CA_NorthCoastRanges_2_B23"


def test_missing_dataset_is_reported(lidar_config):
    lidar_config["noise_floor"]["epoch_pair"] = ["2022", "1999"]
    with pytest.raises(ValueError, match="No dataset for epochs: 1999"):
        noise_floor_projects(lidar_config)


def test_plan_draws_the_requested_tile_count(lidar_config):
    plan = calibration_plan(lidar_config, tile_count=40)
    assert plan["tile_count"] == 40
    assert plan["sample_area_km2"] == pytest.approx(40.0, rel=0.05)


def test_plan_carries_a_reader_per_epoch_per_tile(lidar_config):
    plan = calibration_plan(lidar_config, tile_count=25)
    for tile in plan["tiles"]:
        assert set(tile["readers"]) == {"2022", "2023"}
        for reader in tile["readers"].values():
            assert reader["type"] == "readers.ept"
            assert reader["bounds"].startswith("([")


def test_plan_uses_the_sparsest_epoch_for_the_sampling_radius(lidar_config):
    plan = calibration_plan(lidar_config, tile_count=25)
    assert plan["sample_radius_m"] == pytest.approx(0.2699, abs=1e-3)


def test_plan_spreads_tiles_across_the_calibration_band(lidar_config):
    """Sampling is stratified on a coarse grid, so tiles cannot clump."""
    plan = calibration_plan(lidar_config, tile_count=25)
    longitudes = [tile["box"][0] for tile in plan["tiles"]]
    west, _, east, _ = plan["calibration_box"]
    span = max(longitudes) - min(longitudes)
    assert span > 0.5 * (east - west)


def test_plan_is_deterministic(lidar_config):
    first = calibration_plan(lidar_config, tile_count=20, seed=7)
    second = calibration_plan(lidar_config, tile_count=20, seed=7)
    assert [t["box"] for t in first["tiles"]] == [t["box"] for t in second["tiles"]]


def test_dispersion_grid_never_outnumbers_the_sample():
    for count in (1, 4, 9, 20, 25, 40, 100):
        side = dispersion_grid_side(count)
        assert side * side <= count
    with pytest.raises(ValueError, match="must be positive"):
        dispersion_grid_side(0)


@pytest.mark.parametrize("count", [1, 5, 16, 40, 64])
def test_plan_succeeds_across_sample_sizes(lidar_config, count):
    plan = calibration_plan(lidar_config, tile_count=count)
    assert plan["tile_count"] == count
