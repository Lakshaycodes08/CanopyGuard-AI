from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.raster import block_reduce, shift_bilinear, slope_aspect


def test_block_reduce_averages_whole_blocks():
    grid = np.arange(16, dtype=np.float64).reshape(4, 4)
    reduced = block_reduce(grid, factor=2)
    assert reduced.tolist() == [[2.5, 4.5], [10.5, 12.5]]


def test_block_reduce_trims_a_ragged_edge():
    grid = np.ones((5, 7))
    assert block_reduce(grid, factor=2).shape == (2, 3)


def test_block_reduce_drops_blocks_below_the_valid_fraction():
    grid = np.full((2, 2), np.nan)
    grid[0, 0] = 4.0
    assert np.isnan(block_reduce(grid, 2, min_valid_fraction=0.5)[0, 0])
    assert block_reduce(grid, 2, min_valid_fraction=0.25)[0, 0] == pytest.approx(4.0)


def test_block_reduce_supports_the_upper_percentile():
    grid = np.array([[1.0, 2.0], [3.0, 100.0]])
    assert block_reduce(grid, 2, statistic="p95")[0, 0] > 50.0


def test_block_reduce_rejects_bad_arguments():
    with pytest.raises(ValueError, match="at least one"):
        block_reduce(np.ones((2, 2)), 0)
    with pytest.raises(ValueError, match="one of"):
        block_reduce(np.ones((2, 2)), 2, statistic="mode")
    with pytest.raises(ValueError, match="exceeds the grid"):
        block_reduce(np.ones((2, 2)), 4)


def test_slope_of_a_known_plane():
    """A plane rising one metre east per ten metres is about 5.71 degrees."""
    resolution = 10.0
    columns = np.arange(20, dtype=np.float64)
    plane = np.tile(columns, (20, 1)) * 1.0
    slope, aspect = slope_aspect(plane, resolution)
    assert np.degrees(slope[10, 10]) == pytest.approx(5.7106, abs=1e-3)
    assert np.degrees(aspect[10, 10]) == pytest.approx(270.0, abs=1e-6)


def test_aspect_points_downhill_from_north():
    """A surface falling towards the south has a due-south aspect."""
    rows = np.arange(20, dtype=np.float64).reshape(-1, 1)
    surface = np.tile(-rows, (1, 20))
    _, aspect = slope_aspect(surface, 10.0)
    assert np.degrees(aspect[10, 10]) == pytest.approx(180.0, abs=1e-6)


def test_shift_bilinear_recovers_an_integer_offset():
    grid = np.arange(100, dtype=np.float64).reshape(10, 10)
    shifted = shift_bilinear(grid, dx_m=10.0, dy_m=0.0, resolution=10.0)
    assert shifted[5, 3] == pytest.approx(grid[5, 4])


def test_shift_bilinear_interpolates_a_half_cell():
    grid = np.arange(100, dtype=np.float64).reshape(10, 10)
    shifted = shift_bilinear(grid, dx_m=5.0, dy_m=0.0, resolution=10.0)
    assert shifted[5, 3] == pytest.approx(0.5 * (grid[5, 3] + grid[5, 4]))


def test_shift_bilinear_marks_out_of_range_cells():
    grid = np.arange(100, dtype=np.float64).reshape(10, 10)
    shifted = shift_bilinear(grid, dx_m=30.0, dy_m=0.0, resolution=10.0)
    assert np.isnan(shifted[5, -1])


def test_shift_bilinear_with_zero_shift_keeps_the_last_row_and_column():
    grid = np.arange(100, dtype=np.float64).reshape(10, 10)
    shifted = shift_bilinear(grid, dx_m=0.0, dy_m=0.0, resolution=10.0)
    assert np.array_equal(shifted, grid)


def test_shift_bilinear_is_reversible_in_the_interior():
    rng = np.random.default_rng(0)
    grid = rng.normal(size=(40, 40))
    there = shift_bilinear(grid, 20.0, -10.0, 10.0)
    back = shift_bilinear(there, -20.0, 10.0, 10.0)
    interior = back[5:-5, 5:-5]
    assert np.allclose(interior, grid[5:-5, 5:-5], atol=1e-9)
