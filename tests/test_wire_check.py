import numpy as np

from canopyguard.lidar.wire_check import (
    analysis_rows,
    expected_counts,
    flag_spikes,
    neighbour_median,
    tile_bootstrap_ratio,
    to_grid,
)
from canopyguard.lidar.wire_check_verify import persistence_counts

SPIKE = {
    "min_max_height_m": 10.0,
    "max_neighbour_median_m": 3.0,
    "min_neighbours": 4,
    "wire_like_gap_m": 5.0,
}


def small_grid(values):
    side = values.shape[0]
    rows, cols = np.meshgrid(np.arange(side), np.arange(side), indexing="ij")
    x = ((cols + 0.5) * 10.0).ravel()
    y = ((rows + 0.5) * 10.0).ravel()
    return to_grid(x, y, values.ravel(), 10.0)


def test_planted_wire_cell_is_flagged_and_tree_is_not():
    heights = np.full((5, 5), 1.0)
    heights[2, 2] = 25.0
    tree = np.full((5, 5), 20.0)
    for values, expected in ((heights, True), (tree, False)):
        grid, col, row = small_grid(values)
        median = neighbour_median(grid, col, row, 4)
        top = grid[row, col]
        isolated, _ = flag_spikes(top, top - 8.0, median, SPIKE)
        centre = np.flatnonzero((row == 3) & (col == 3))[0]
        assert bool(isolated[centre]) is expected


def test_edge_cells_with_few_neighbours_are_not_flagged():
    grid, col, row = small_grid(np.full((3, 3), 30.0))
    median = neighbour_median(grid, col, row, 4)
    corner = np.flatnonzero((row == 1) & (col == 1))[0]
    assert np.isnan(median[corner])


def test_expected_counts_use_only_strata_with_controls():
    key = np.array([0, 0, 1, 1, 1])
    flag = np.array([1.0, 0, 0, 0, 1])
    near = np.array([True, False, True, False, False])
    control = np.array([False, False, False, True, True])
    obs, exp, n_near = expected_counts(key, flag, near, control)
    assert obs.tolist() == [0.0, 0.0]
    assert n_near.tolist() == [0.0, 1.0]
    assert exp[1] == 0.5


def test_bootstrap_ratio_of_equal_rates_is_one():
    tiles = np.arange(40)
    obs = np.ones(40)
    ratio, low, high = tile_bootstrap_ratio(tiles, obs, obs.copy(), 500, 0.95, 1)
    assert ratio == 1.0
    assert low <= 1.0 <= high


def raw_table():
    return {
        "cell_id": np.array([1, 2, 2, 3]),
        "valid_start": np.array([0.9, 0.9, 0.6, 0.9]),
        "valid_end": np.array([0.9, 0.9, 0.7, 0.9]),
        "tile": np.array([10, 11, 12, 13]),
        "mean_change": np.array([0.0, 1.0, 2.0, np.nan]),
    }


def test_raw_archive_drops_repeats_and_disputed_cells():
    rows, disputed = analysis_rows(raw_table())
    assert disputed == 1
    assert rows.tolist() == [0]


def test_unique_archive_uses_the_disputed_flag():
    table = raw_table()
    table["overlap_disputed"] = np.array([False, True, False, False])
    rows, disputed = analysis_rows(table)
    assert disputed == 1
    assert rows.tolist() == [0, 2]


def test_persistence_counts_split_flags_by_epoch():
    first = np.array([True, True, False, False])
    second = np.array([True, False, True, False])
    out = persistence_counts(first, second, np.array([True, True, True, True]))
    assert out == {
        "first": 2,
        "second": 2,
        "both": 1,
        "only_first": 1,
        "only_second": 1,
    }
