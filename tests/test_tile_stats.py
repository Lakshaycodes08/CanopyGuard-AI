from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar import tile_stats
from canopyguard.lidar.ept import to_web_mercator
from canopyguard.lidar.tile_stats import PointRules

RULES = PointRules(
    noise_classes=(7, 18), water_class=9, ground_class=2, excluded_flag_bits=13
)
TILES = [(-122.00, 38.00, -121.99, 38.01), (-121.99, 38.00, -121.98, 38.01)]


def points(lonlat_z_class_flag):
    rows = list(lonlat_z_class_flag)
    xy = [to_web_mercator(lon, lat) for lon, lat, *_ in rows]
    return {
        "x": np.array([p[0] for p in xy]),
        "y": np.array([p[1] for p in xy]),
        "z": np.array([row[2] for row in rows], dtype=float),
        "classification": np.array([row[3] for row in rows], dtype=np.uint8),
        "flags": np.array([row[4] for row in rows], dtype=np.uint8),
    }


def test_mercator_to_lonlat_inverts_the_forward_conversion() -> None:
    x, y = to_web_mercator(-122.3, 38.7)

    lon, lat = tile_stats.mercator_to_lonlat(np.array([x]), np.array([y]))

    assert lon[0] == pytest.approx(-122.3)
    assert lat[0] == pytest.approx(38.7)


def test_locate_assigns_tile_and_cell_and_marks_outside_points() -> None:
    grid = tile_stats.make_tile_grid(TILES, cells=2)
    lon = np.array([-121.9925, -121.9825, -122.5])
    lat = np.array([38.0025, 38.0075, 38.0025])

    tile, row, column = tile_stats.locate(grid, lon, lat)

    assert tile.tolist() == [0, 1, -1]
    assert (row[0], column[0]) == (0, 1)
    assert (row[1], column[1]) == (1, 1)


def test_add_points_counts_ground_surface_and_skips_noise_and_flagged() -> None:
    grid = tile_stats.make_tile_grid(TILES, cells=2)
    stats = tile_stats.TileStats(2, 2)
    lon, lat = -121.9925, 38.0025
    kept = tile_stats.add_points(
        stats,
        grid,
        points(
            [
                (lon, lat, 100.0, 2, 0),
                (lon, lat, 102.0, 2, 0),
                (lon, lat, 110.0, 1, 0),
                (lon, lat, 140.0, 7, 0),
                (lon, lat, 130.0, 9, 0),
                (lon, lat, 120.0, 1, 8),
                (-122.5, 38.0025, 1.0, 2, 0),
            ]
        ),
        RULES,
    )

    assert kept == 3
    assert stats.point_count[0, 0, 1] == 3
    assert stats.ground_count[0, 0, 1] == 2
    assert tile_stats.ground_surface(stats)[0, 0, 1] == pytest.approx(101.0)
    assert tile_stats.heights_above_ground(stats)[0, 0, 1] == pytest.approx(9.0)
    assert np.isnan(tile_stats.heights_above_ground(stats)[0, 0, 0])


def test_height_is_never_negative() -> None:
    grid = tile_stats.make_tile_grid(TILES, cells=1)
    stats = tile_stats.TileStats(2, 1)
    tile_stats.add_points(
        stats,
        grid,
        points([(-121.995, 38.005, 100, 2, 0), (-121.995, 38.005, 99, 1, 0)]),
        RULES,
    )

    assert tile_stats.heights_above_ground(stats)[0, 0, 0] == 0.0


def test_tile_validity_needs_returns_and_ground_in_enough_cells() -> None:
    stats = tile_stats.TileStats(2, 2)
    stats.point_count[0] = 5
    stats.ground_count[0] = [[1, 1], [0, 0]]
    stats.point_count[1, 0, 0] = 5

    result = tile_stats.tile_validity(stats, 0.9, 0.5)

    assert result["valid"].tolist() == [True, False]
    assert result["cell_fraction"].tolist() == [1.0, 0.25]


def test_slope_of_a_tilted_plane() -> None:
    columns = np.arange(5) * 10.0
    plane = np.broadcast_to(0.1 * columns, (1, 5, 5)).copy()

    slope = tile_stats.slope_degrees(plane, 10.0)

    assert np.degrees(np.arctan(0.1)) == pytest.approx(5.71, abs=0.01)
    assert slope[0, 2, 2] == pytest.approx(5.71, abs=0.01)


def test_cell_centres_sit_inside_each_tile() -> None:
    grid = tile_stats.make_tile_grid(TILES, cells=2)

    lon, lat = tile_stats.cell_centres(grid)

    assert lon[0, 0, 0] == pytest.approx(-121.9975)
    assert lat[0, 1, 0] == pytest.approx(38.0075)
    assert lon[1, 0, 1] == pytest.approx(-121.9825)


def test_make_tile_grid_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="At least one tile"):
        tile_stats.make_tile_grid([], 5)
