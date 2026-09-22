from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.difference import (
    aggregate_ladder,
    annualise,
    apply_mask,
    difference,
    difference_ladder,
    scale_factor,
    summarise,
)


def test_scale_factor_from_the_base_grid():
    assert scale_factor(1.0, 10.0) == 10
    assert scale_factor(10.0, 100.0) == 10


def test_scale_factor_rejects_a_non_multiple():
    with pytest.raises(ValueError, match="not a multiple"):
        scale_factor(10.0, 25.0)


def test_aggregate_ladder_produces_every_requested_scale():
    grid = np.ones((100, 100))
    ladder = aggregate_ladder(grid, 1.0, [1.0, 10.0, 50.0])
    assert ladder[1.0].shape == (100, 100)
    assert ladder[10.0].shape == (10, 10)
    assert ladder[50.0].shape == (2, 2)


def test_difference_is_later_minus_earlier():
    assert difference(np.full((2, 2), 10.0), np.full((2, 2), 13.0))[0, 0] == 3.0


def test_difference_rejects_mismatched_grids():
    with pytest.raises(ValueError, match="share a grid"):
        difference(np.ones((2, 2)), np.ones((3, 3)))


def test_difference_ladder_recovers_a_uniform_change():
    start = np.full((40, 40), 20.0)
    end = np.full((40, 40), 23.0)
    ladder = difference_ladder(start, end, 1.0, [1.0, 10.0, 20.0])
    for grid in ladder.values():
        assert np.allclose(grid, 3.0)


def test_aggregation_does_not_let_one_epoch_borrow_coverage():
    """A cell thin in the earlier epoch stays no-data after differencing."""
    start = np.full((10, 10), np.nan)
    start[0, 0] = 20.0
    end = np.full((10, 10), 23.0)
    ladder = difference_ladder(start, end, 1.0, [10.0], min_valid_fraction=0.5)
    assert np.isnan(ladder[10.0][0, 0])


def test_annualise_divides_by_the_baseline():
    assert annualise(np.array([4.5]), 9.0)[0] == pytest.approx(0.5)
    with pytest.raises(ValueError, match="must be positive"):
        annualise(np.array([1.0]), 0.0)


def test_apply_mask_blanks_cells_outside_the_stratum():
    delta = np.array([[1.0, 2.0], [3.0, 4.0]])
    keep = np.array([[True, False], [False, True]])
    masked = apply_mask(delta, keep)
    assert masked[0, 0] == 1.0
    assert np.isnan(masked[0, 1])


def test_summarise_reports_location_and_spread():
    rng = np.random.default_rng(0)
    delta = rng.normal(loc=3.0, scale=1.0, size=5000)
    stats = summarise(delta)
    assert stats["mean_m"] == pytest.approx(3.0, abs=0.1)
    assert stats["sd_m"] == pytest.approx(1.0, abs=0.1)
    assert stats["cells"] == 5000


def test_summarise_ignores_no_data():
    assert summarise(np.array([1.0, np.nan, 3.0]))["cells"] == 2
    with pytest.raises(ValueError, match="no valid cells"):
        summarise(np.array([np.nan, np.nan]))
