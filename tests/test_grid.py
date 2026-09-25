from __future__ import annotations

import pytest

from canopyguard.lidar.grid import (
    grid_box,
    grid_geometry,
    project_box,
    tile_grid_geometry,
)


def test_grid_origin_snaps_outward_to_the_resolution():
    grid = grid_geometry((100.4, 200.9, 350.2, 460.1), 1.0)
    assert grid["origin_x"] == 100.0
    assert grid["origin_y"] == 200.0
    assert grid["width"] == 251
    assert grid["height"] == 261


def test_grid_covers_the_whole_box():
    box = (100.4, 200.9, 350.2, 460.1)
    covered = grid_box(grid_geometry(box, 2.0))
    assert covered[0] <= box[0] and covered[1] <= box[1]
    assert covered[2] >= box[2] and covered[3] >= box[3]


def test_both_epochs_of_a_tile_get_one_grid():
    """The grid comes from the tile box, not from the points that arrive."""
    box = (100.0, 200.0, 300.0, 400.0)
    assert grid_geometry(box, 1.0) == grid_geometry(box, 1.0)


def test_neighbouring_tiles_land_on_one_lattice():
    left = grid_geometry((100.3, 200.0, 200.3, 300.0), 1.0)
    right = grid_geometry((200.3, 200.0, 300.3, 300.0), 1.0)
    assert (right["origin_x"] - left["origin_x"]) % 1.0 == 0.0
    assert (right["origin_y"] - left["origin_y"]) % 1.0 == 0.0


def test_grid_rejects_a_degenerate_box():
    with pytest.raises(ValueError, match="min < max"):
        grid_geometry((10.0, 10.0, 10.0, 20.0), 1.0)


def test_grid_rejects_a_non_positive_resolution():
    with pytest.raises(ValueError, match="Resolution must be positive"):
        grid_geometry((0.0, 0.0, 10.0, 10.0), 0.0)


def test_grid_rejects_an_empty_raster():
    with pytest.raises(ValueError, match="min < max"):
        grid_geometry((0.0, 0.0, 0.0, 0.0), 1.0)


def test_projected_box_encloses_the_corner_projection():
    """A rectangle in degrees is not a rectangle in a projected frame."""
    box = (-123.0, 38.0, -122.0, 39.0)
    dense = project_box(box, "EPSG:6339", samples_per_edge=51)
    corners = project_box(box, "EPSG:6339", samples_per_edge=2)
    assert dense[0] <= corners[0]
    assert dense[1] <= corners[1]
    assert dense[2] >= corners[2]
    assert dense[3] >= corners[3]


def test_projected_box_rejects_too_few_samples():
    with pytest.raises(ValueError, match="at least two samples"):
        project_box((-123.0, 38.0, -122.0, 39.0), "EPSG:6339", samples_per_edge=1)


def test_projected_box_rejects_an_inverted_box():
    with pytest.raises(ValueError, match="west < east"):
        project_box((-122.0, 38.0, -123.0, 39.0), "EPSG:6339")


def test_tile_grid_geometry_matches_the_tile_size():
    grid = tile_grid_geometry(
        (-122.8400, 38.5400, -122.8371, 38.5422), "EPSG:6339", 1.0
    )
    assert 230 <= grid["width"] <= 270
    assert 230 <= grid["height"] <= 270


def test_grid_snaps_origin_and_extent_to_the_global_cell():
    from canopyguard.lidar.grid import grid_geometry

    grid = grid_geometry((500007.3, 4270011.0, 500498.2, 4270505.5), 1.0, 30.0)
    assert (grid["origin_x"], grid["origin_y"]) == (499980.0, 4269990.0)
    assert grid["width"] % 30 == 0 and grid["height"] % 30 == 0
    assert grid["origin_x"] + grid["width"] >= 500498.2
    with pytest.raises(ValueError, match="multiple of the resolution"):
        grid_geometry((0.0, 0.0, 10.0, 10.0), 1.0, 2.5)
