from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar import pair_tiles, tile_stats
from canopyguard.lidar.pair_tiles import PairRules

TILES = [(-122.0, 38.0, -121.99, 38.01), (-121.99, 38.0, -121.98, 38.01)]
RULES = PairRules(
    min_cell_fraction=0.9,
    min_ground_fraction=0.5,
    canopy_min_m=2.0,
    disturbance_limit_m=3.0,
    height_classes_m=(2.0, 5.0, 15.0),
    slope_bands_deg=((0.0, 15.0), (15.0, 90.0)),
    cell_m=10.0,
)


def epoch(ground: float, top: np.ndarray, tiles_with_data: tuple[int, ...] = (0, 1)):
    """Statistics where every cell of the chosen tiles has ground and a top return."""
    stats = tile_stats.TileStats(2, 2)
    for tile in tiles_with_data:
        stats.point_count[tile] = 4
        stats.ground_count[tile] = 2
        stats.ground_sum[tile] = ground * 2
        stats.surface_max[tile] = ground + top
    return stats


def run(earlier, later, burned=None, minimum=0.0001):
    grid = tile_stats.make_tile_grid(TILES, 2)
    burned = np.zeros((2, 2, 2), dtype=bool) if burned is None else burned
    return pair_tiles.analyse_pair(grid, earlier, later, RULES, burned, minimum)


def test_canopy_in_both_epochs_is_counted_by_cell_area() -> None:
    result = run(epoch(100, np.full((2, 2), 10.0)), epoch(100, np.full((2, 2), 12.0)))

    cell = (10.0 / 1000.0) ** 2
    assert result["tiles"]["valid_both"] == 2
    assert result["area_km2"]["canopy_both"] == pytest.approx(8 * cell)
    assert result["usable_canopy_km2"] == pytest.approx(8 * cell)
    assert result["lidar_height_change_m_on_undisturbed"]["median"] == pytest.approx(
        2.0
    )


def test_loss_beyond_the_limit_is_excluded_from_usable_canopy() -> None:
    early = epoch(100, np.full((2, 2), 10.0))
    late = epoch(100, np.full((2, 2), 10.0))
    late.surface_max[1] = 100 + 3.0

    result = run(early, late)

    cell = (10.0 / 1000.0) ** 2
    assert result["area_km2"]["lost"] == pytest.approx(4 * cell)
    assert result["usable_canopy_km2"] == pytest.approx(4 * cell)


def test_burned_cells_are_not_usable() -> None:
    burned = np.zeros((2, 2, 2), dtype=bool)
    burned[0] = True

    result = run(
        epoch(100, np.full((2, 2), 10.0)), epoch(100, np.full((2, 2), 10.0)), burned
    )

    cell = (10.0 / 1000.0) ** 2
    assert result["area_km2"]["burned_canopy"] == pytest.approx(4 * cell)
    assert result["usable_canopy_km2"] == pytest.approx(4 * cell)


def test_tile_missing_in_one_epoch_is_not_valid_for_the_pair() -> None:
    result = run(
        epoch(100, np.full((2, 2), 10.0), tiles_with_data=(0,)),
        epoch(100, np.full((2, 2), 10.0)),
    )

    assert result["tiles"] == {
        "candidates": 2,
        "valid_earlier": 1,
        "valid_later": 2,
        "valid_both": 1,
    }
    assert result["tile_rows"][1]["valid_earlier"] is False


def test_gate_compares_usable_canopy_with_the_minimum() -> None:
    small = run(
        epoch(100, np.full((2, 2), 10.0)),
        epoch(100, np.full((2, 2), 10.0)),
        minimum=5.0,
    )
    assert small["usable_canopy_meets_minimum"] is False


def test_height_classes_split_canopy_area() -> None:
    result = run(epoch(100, np.full((2, 2), 10.0)), epoch(100, np.full((2, 2), 10.0)))

    mix = result["canopy_height_class_km2"]
    assert list(mix) == ["2-5 m", "5-15 m", "15 m and above"]
    assert mix["5-15 m"] == pytest.approx(8 * (10.0 / 1000.0) ** 2)
    assert mix["2-5 m"] == 0.0


def test_terrain_mix_reports_bands_and_elevation() -> None:
    later = epoch(100, np.full((2, 2), 10.0))

    result = run(epoch(100, np.full((2, 2), 10.0)), later)

    assert result["terrain"]["ground_elevation_m"] == [100.0, 100.0, 100.0]
    assert result["terrain"]["slope_band_km2"]["0-15 deg"] > 0.0
