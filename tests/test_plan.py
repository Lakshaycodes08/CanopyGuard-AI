from __future__ import annotations

import pytest

from canopyguard.config import load_config
from canopyguard.lidar.ept import to_web_mercator
from canopyguard.lidar.plan import (
    calibration_plan,
    calibration_tiles,
    change_plan,
    epoch_unit_stages,
    change_tiles,
    dispersion_grid_side,
    epoch_datasets,
    epoch_footprint,
    epoch_resource_footprints,
    noise_floor_projects,
    pair_projects,
    search_box,
    tile_resources,
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
    assert plan["sample_radius_m"] == pytest.approx(0.2258, abs=1e-3)


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


SONOMA_2013 = [
    "USGS_LPC_CA_Sonoma_A2_2013_LAS_2017",
    "USGS_LPC_CA_Sonoma_A3_2013_LAS_2017",
    "USGS_LPC_CA_Sonoma_A4_2013_LAS_2017",
]
STUDY_BOX = (-122.90, 38.475, -122.74, 38.82)


@pytest.fixture
def resource_boxes():
    """The 2013 epoch as three abutting resources, the 2022 epoch as one."""
    return {
        SONOMA_2013[0]: delivery_grid(-122.92, 38.46, -122.82, 38.66),
        SONOMA_2013[1]: delivery_grid(-122.82, 38.46, -122.72, 38.66),
        SONOMA_2013[2]: delivery_grid(-122.92, 38.66, -122.72, 38.84),
        "CA_NorthernCA_1_B22": delivery_grid(-122.92, 38.46, -122.72, 38.84),
    }


def test_epoch_datasets_accepts_one_name_or_several():
    assert epoch_datasets({"name": "a", "dataset": "X"}) == ["X"]
    assert epoch_datasets({"name": "a", "datasets": ["X", "Y"]}) == ["X", "Y"]
    with pytest.raises(ValueError, match="names no dataset"):
        epoch_datasets({"name": "a"})


def test_the_2013_epoch_is_three_resources(lidar_config):
    projects = pair_projects(lidar_config, ["2013", "2022"])
    assert projects["2013"] == SONOMA_2013
    assert projects["2022"] == ["CA_NorthernCA_1_B22"]


def test_a_noise_floor_epoch_must_be_one_resource(lidar_config):
    lidar_config["noise_floor"]["epoch_pair"] = ["2013", "2022"]
    with pytest.raises(ValueError, match="must name one dataset: 2013"):
        noise_floor_projects(lidar_config)


def test_a_change_pair_names_two_epochs(lidar_config):
    with pytest.raises(ValueError, match="two different epochs"):
        pair_projects(lidar_config, ["2013", "2013"])


def test_missing_resource_footprint_is_reported(lidar_config, resource_boxes):
    projects = pair_projects(lidar_config, ["2013", "2022"])
    del resource_boxes[SONOMA_2013[1]]
    with pytest.raises(ValueError, match="No footprint for resources"):
        epoch_resource_footprints(projects, resource_boxes)


def test_an_epoch_footprint_joins_its_resources(lidar_config, resource_boxes):
    projects = pair_projects(lidar_config, ["2013", "2022"])
    by_epoch = epoch_resource_footprints(projects, resource_boxes)
    joined = epoch_footprint(by_epoch["2013"])
    assert len(joined) == sum(len(resource_boxes[name]) for name in SONOMA_2013)


def test_tile_resources_names_only_the_resources_meeting_the_tile(resource_boxes):
    by_resource = {name: resource_boxes[name] for name in SONOMA_2013}
    assert tile_resources((-122.90, 38.50, -122.89, 38.51), by_resource) == [
        SONOMA_2013[0]
    ]
    assert tile_resources((-122.83, 38.50, -122.81, 38.51), by_resource) == [
        SONOMA_2013[0],
        SONOMA_2013[1],
    ]
    assert tile_resources((-121.0, 38.50, -120.9, 38.51), by_resource) == []


def test_change_tiles_lie_inside_the_study_box(lidar_config, resource_boxes):
    projects = pair_projects(lidar_config, ["2013", "2022"])
    by_epoch = epoch_resource_footprints(projects, resource_boxes)
    tiles = change_tiles(
        lidar_config,
        STUDY_BOX,
        {epoch: epoch_footprint(boxes) for epoch, boxes in by_epoch.items()},
    )
    assert tiles
    for west, south, east, north in tiles:
        assert west >= STUDY_BOX[0] and east <= STUDY_BOX[2]
        assert south >= STUDY_BOX[1] and north <= STUDY_BOX[3]


def test_change_plan_carries_reader_lists(lidar_config, resource_boxes):
    plan = change_plan(lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 30)
    assert plan["tile_count"] == 30
    assert plan["tile_size_m"] == 500.0
    assert plan["pair"] == ["2013", "2022"]
    assert plan["sample_radius_m"] == pytest.approx(0.2258, abs=1e-3)
    for tile in plan["tiles"]:
        assert set(tile["readers"]) == {"2013", "2022"}
        assert len(tile["readers"]["2022"]) == 1
        assert tile["readers"]["2013"][-1]["type"] == "filters.assign"
        assert 1 <= len(tile["readers"]["2013"]) - 1 <= 3
        for readers in tile["readers"].values():
            for reader in readers:
                assert reader["type"] in {"readers.ept", "filters.assign"}
        assert 460 <= tile["grid"]["width"] <= 540


def test_change_plan_refuses_a_pair_without_co_coverage(lidar_config, resource_boxes):
    resource_boxes["CA_NorthernCA_1_B22"] = delivery_grid(
        -121.50, 38.46, -121.30, 38.84
    )
    with pytest.raises(ValueError, match="both epochs of the pair"):
        change_plan(lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 10)


def test_change_plan_is_deterministic(lidar_config, resource_boxes):
    first = change_plan(lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 20)
    second = change_plan(
        lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 20
    )
    assert [tile["box"] for tile in first["tiles"]] == [
        tile["box"] for tile in second["tiles"]
    ]


def test_epoch_unit_stages_convert_only_declared_epochs():
    config = {"epochs": [{"name": "2013", "z_to_metres": 0.3048}, {"name": "2022"}]}
    assert epoch_unit_stages(config, "2013")[0]["type"] == "filters.assign"
    assert epoch_unit_stages(config, "2022") == []
    with pytest.raises(ValueError, match="No epoch named"):
        epoch_unit_stages(config, "2030")


def test_corridor_tiles_are_always_built(lidar_config, resource_boxes):
    from canopyguard.lidar.plan import corridor_tiles

    line = {"lon": [-122.85, -122.80], "lat": [38.60, 38.60]}
    plan = change_plan(
        lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 5,
        corridor=([line], 100.0),
    )
    assert plan["required_tiles"] >= 8
    assert plan["tile_count"] == plan["required_tiles"] + 5
    forced = [tuple(t["box"]) for t in plan["tiles"][: plan["required_tiles"]]]
    for west, south, east, north in forced:
        assert south - 0.002 <= 38.60 <= north + 0.002
    assert corridor_tiles(forced, [], 100.0, "EPSG:6339") == []
    for tile in plan["tiles"]:
        assert tile["grid"]["origin_x"] % 30 == 0
        assert tile["grid"]["width"] % 30 == 0


def test_corridor_only_plan_draws_nothing_else(lidar_config, resource_boxes):
    line = {"lon": [-122.85, -122.80], "lat": [38.60, 38.60]}
    plan = change_plan(
        lidar_config, STUDY_BOX, ("2013", "2022"), resource_boxes, 0,
        corridor=([line], 100.0),
    )
    assert plan["tile_count"] == plan["required_tiles"]
