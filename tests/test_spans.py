import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from canopyguard.risk.spans import (
    assign_pixels,
    cut_segments,
    random_recall,
    segment_scores,
)

TRUTH = {"min_canopy_share": 0.3, "min_pixels_per_segment": 2}


def test_lines_are_cut_into_near_equal_pieces():
    segments = cut_segments([LineString([(0, 0), (1000, 0)])], 300)
    assert len(segments) == 3
    assert segments["length_m"].sum() == pytest.approx(1000.0)


def test_pixels_go_to_the_nearest_segment_within_the_half_width():
    segments = cut_segments([LineString([(0, 0), (600, 0)])], 300)
    east = np.array([100.0, 500.0, 100.0])
    north = np.array([10.0, -20.0, 200.0])
    assigned = assign_pixels(east, north, segments, half_width_m=60.0)
    assert assigned.tolist() == [0, 1, -1]


def test_segment_scores_use_canopy_pixels_only():
    segments = cut_segments([LineString([(0, 0), (300, 0)])], 300)
    pixels = pd.DataFrame(
        {
            "y": [1.0, 3.0, 9.0],
            "p95_change": [1.0, 3.0, 9.0],
            "p95_start": [10.0, 20.0, 0.0],
            "canopy_share": [1.0, 1.0, 0.0],
            "pred_a": [2.0, 2.0, 50.0],
        }
    )
    table = segment_scores(pixels, np.array([0, 0, 0]), segments, ["pred_a"], TRUTH)
    assert table.loc[0, "truth_mean_change"] == pytest.approx(2.0)
    assert table.loc[0, "pred_a"] == pytest.approx(2.0)
    assert table.loc[0, "n_pixels"] == 2


def test_random_ranking_recovers_the_budget_fraction():
    labels = np.array([1.0] * 20 + [0.0] * 80)
    weights = np.ones(100)
    value = random_recall(labels, weights, 0.2, draws=300, seed=1)
    assert value == pytest.approx(0.2, abs=0.05)
