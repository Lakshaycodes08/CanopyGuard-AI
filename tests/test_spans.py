import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from canopyguard.risk.spans import (
    assign_pixels,
    cut_segments,
    evaluate_ranking,
    random_recall,
    segment_table,
)


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


def test_segment_table_averages_only_the_pixels_it_is_given():
    segments = cut_segments([LineString([(0, 0), (300, 0)])], 300)
    pixels = pd.DataFrame({"y": [1.0, 3.0], "pred": [2.0, 4.0]})
    table = segment_table(pixels, np.array([0, 0]), segments, ["y", "pred"], 2)
    assert table.loc[0, "y"] == pytest.approx(2.0)
    assert table.loc[0, "pred"] == pytest.approx(3.0)
    assert table.loc[0, "n_pixels"] == 2
    short = segment_table(pixels, np.array([0, -1]), segments, ["y"], 2)
    assert short.empty


def test_random_ranking_recovers_the_budget_fraction():
    labels = np.array([1.0] * 20 + [0.0] * 80)
    value = random_recall(labels, np.ones(100), 0.2, draws=300, seed=1)
    assert value == pytest.approx(0.2, abs=0.05)


def test_a_perfect_score_beats_an_inverted_one_in_the_ranking_report():
    truth = np.linspace(0.0, 1.0, 50)
    table = pd.DataFrame(
        {
            "truth": truth,
            "good": truth,
            "bad": -truth,
            "length_m": 300.0,
            "block": np.repeat(np.arange(10), 5),
        }
    )
    cfg = {
        "truth": {"high_quantile": 0.8},
        "ranking": {
            "k_fractions": [0.2],
            "random_draws": 50,
            "bootstrap_resamples": 50,
            "confidence_level": 0.9,
        },
    }
    result = evaluate_ranking(
        table, "truth", {"good": "good", "bad": "bad"}, "good", ["bad"], cfg, seed=1
    )
    assert result["scores"]["good"]["recall_at_20pct"] == pytest.approx(1.0)
    assert result["scores"]["bad"]["recall_at_20pct"] == pytest.approx(0.0)
    gap = result["contrasts"]["good_minus_bad_recall_at_20pct"]
    assert gap["difference"] == pytest.approx(1.0)
