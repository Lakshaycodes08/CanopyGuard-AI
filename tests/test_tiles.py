from __future__ import annotations

import pytest

from canopyguard.lidar.tiles import sample_area_km2, stratified_sample, tile_grid

CALIBRATION = (-123.39, 38.79, -122.36, 38.93)


def test_tile_grid_covers_the_box_with_roughly_square_tiles():
    tiles = tile_grid(CALIBRATION, 1000.0)
    assert len(tiles) > 1000
    west, south, east, north = tiles[0]
    assert sample_area_km2([tiles[0]]) == pytest.approx(1.0, rel=0.02)


def test_tile_grid_returns_one_tile_for_a_small_box():
    assert len(tile_grid((-122.80, 38.80, -122.799, 38.801), 1000.0)) == 1


def test_tile_grid_rejects_bad_input():
    with pytest.raises(ValueError, match="west < east"):
        tile_grid((1.0, 0.0, 0.0, 1.0), 1000.0)
    with pytest.raises(ValueError, match="must be positive"):
        tile_grid(CALIBRATION, 0.0)


def test_tile_grid_covers_a_final_partial_strip():
    box = (-122.80, 38.80, -122.799, 38.8035)  # north-south extent is 3.5 rows
    tiles = tile_grid(box, 100.0)
    norths = [tile[3] for tile in tiles]
    assert max(norths) == pytest.approx(box[3])


def test_sample_area_sums_the_tiles():
    tiles = tile_grid(CALIBRATION, 1000.0)
    assert sample_area_km2(tiles) == pytest.approx(len(tiles), rel=0.05)


def test_stratified_sample_covers_every_occupied_stratum():
    items = [f"{group}-{index}" for group in "abcd" for index in range(50)]
    sample = stratified_sample(items, lambda item: item.split("-")[0], 12)
    assert len(sample) == 12
    assert {item.split("-")[0] for item in sample} == set("abcd")


def test_rare_stratum_is_never_dropped():
    items = ["common"] * 500 + ["rare"]
    sample = stratified_sample(items, lambda item: item, 40)
    assert "rare" in sample


def test_allocation_follows_stratum_size():
    items = ["big"] * 900 + ["small"] * 100
    sample = stratified_sample(items, lambda item: item, 50)
    assert sample.count("big") > sample.count("small")
    assert sample.count("small") >= 1


def test_sample_is_deterministic_for_a_fixed_seed():
    items = [f"t{index}" for index in range(200)]
    first = stratified_sample(items, lambda item: item[1], 20, seed=7)
    second = stratified_sample(items, lambda item: item[1], 20, seed=7)
    assert first == second


def test_sample_count_below_stratum_count_is_rejected():
    items = [f"{group}" for group in "abcdef"]
    with pytest.raises(ValueError, match="cannot cover"):
        stratified_sample(items, lambda item: item, 3)


def test_sample_rejects_an_empty_collection():
    with pytest.raises(ValueError, match="empty collection"):
        stratified_sample([], lambda item: item, 5)
