from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.change_table import (
    cell_targets,
    flatten,
    optical_features,
    terrain_features,
    trend,
)


def test_cell_targets_aggregate_blocks():
    start = np.full((4, 4), 10.0)
    end = np.full((4, 4), 11.0)
    end[0, 0] = 2.0
    start[3, 3] = 0.5
    targets = cell_targets(start, end, 2)
    assert targets["change"].shape == (2, 2)
    assert targets["change"][1, 0] == pytest.approx(1.0)
    assert targets["loss_fraction"][0, 0] == pytest.approx(0.25)
    assert targets["canopy_fraction"][1, 1] == pytest.approx(0.75)


def test_cell_targets_require_valid_cover_in_each_epoch():
    start = np.full((2, 2), 5.0)
    end = np.full((2, 2), np.nan)
    end[0, 0] = 6.0
    assert np.isnan(cell_targets(start, end, 2)["change"][0, 0])
    with pytest.raises(ValueError, match="share a grid"):
        cell_targets(np.zeros((2, 2)), np.zeros((3, 3)), 1)


def test_terrain_features_on_a_plane_facing_east():
    x = np.tile(np.arange(60.0), (60, 1))
    features = terrain_features(-0.1 * x, 30, 1.0)
    assert features["elevation"].shape == (2, 2)
    assert features["slope_deg"][0, 0] == pytest.approx(np.degrees(np.arctan(0.1)))
    assert features["eastness"][0, 0] == pytest.approx(1.0)


def test_trend_ignores_missing_years_and_needs_three():
    values = {
        2013: np.array([1.0, 1.0]),
        2014: np.array([2.0, np.nan]),
        2015: np.array([np.nan, np.nan]),
        2016: np.array([4.0, 4.0]),
    }
    slope = trend(values)
    assert slope[0] == pytest.approx(1.0)
    assert np.isnan(slope[1])


def test_optical_features_build_start_end_difference_and_trend():
    stacks = {
        year: {
            "ndvi": np.array([0.1 * (year - 2012)]),
            "nbr": np.array([0.2]),
            "ndmi": np.array([0.3]),
            "clear_count": np.array([5.0]),
        }
        for year in range(2013, 2017)
    }
    features = optical_features(stacks, 2013, 2016)
    assert features["ndvi_diff"][0] == pytest.approx(0.3)
    assert features["ndvi_trend"][0] == pytest.approx(0.1)
    assert "clear_count_start" not in features
    with pytest.raises(ValueError, match="No composite for 2020"):
        optical_features(stacks, 2013, 2020)


def test_flatten_labels_every_cell():
    table = flatten(7, {"a": np.ones((2, 3)), "b": np.zeros((2, 3))})
    assert table["tile"].tolist() == [7.0] * 6
    assert table["row"].tolist() == [0, 0, 0, 1, 1, 1]
    with pytest.raises(ValueError, match="share a grid"):
        flatten(1, {"a": np.ones((2, 3)), "b": np.ones((3, 2))})
