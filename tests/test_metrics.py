from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.metrics import (
    augc,
    average_ranks,
    bias,
    gain_curve,
    mae,
    precision_at_k,
    prevalence,
    r2,
    recall_at_k,
    rmse,
    spearman,
)


def test_regression_metrics_on_known_values():
    truth = [1.0, 2.0, 3.0, 4.0]
    prediction = [1.5, 2.5, 2.5, 4.5]
    assert mae(truth, prediction) == pytest.approx(0.5)
    assert rmse(truth, prediction) == pytest.approx(0.5)
    assert bias(truth, prediction) == pytest.approx(0.25)


def test_r2_is_one_for_exact_prediction():
    truth = [1.0, 2.0, 3.0]
    assert r2(truth, truth) == pytest.approx(1.0)


def test_r2_rejects_constant_truth():
    with pytest.raises(ValueError, match="zero variance"):
        r2([2.0, 2.0], [1.0, 3.0])


def test_metrics_reject_shape_mismatch():
    with pytest.raises(ValueError, match="same shape"):
        mae([1.0, 2.0], [1.0])


def test_average_ranks_handles_ties():
    assert average_ranks([10.0, 20.0, 20.0, 40.0]).tolist() == [1.0, 2.5, 2.5, 4.0]


def test_spearman_detects_monotone_relationships():
    values = np.arange(10.0)
    assert spearman(values, values**3) == pytest.approx(1.0)
    assert spearman(values, -values) == pytest.approx(-1.0)


def test_perfect_ranking_reaches_full_recall_at_its_own_share():
    scores = [9.0, 8.0, 7.0, 1.0, 0.5, 0.2, 0.1, 0.0, -1.0, -2.0]
    labels = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    assert recall_at_k(scores, labels, 0.3) == pytest.approx(1.0)
    assert precision_at_k(scores, labels, 0.3) == pytest.approx(1.0)


def test_inverted_ranking_captures_nothing_early():
    scores = [0.0, 0.1, 0.2, 9.0, 9.1, 9.2]
    labels = [1, 1, 1, 0, 0, 0]
    assert recall_at_k(scores, labels, 0.5) == pytest.approx(0.0)


def test_weights_make_long_units_consume_budget_faster():
    scores = [3.0, 2.0, 1.0, 0.0]
    labels = [0, 1, 0, 0]
    lengths = [900.0, 50.0, 25.0, 25.0]
    assert recall_at_k(scores, labels, 0.5, weights=lengths) == pytest.approx(0.0)
    assert recall_at_k(scores, labels, 0.95, weights=lengths) == pytest.approx(1.0)


def test_gain_curve_is_monotone_and_ends_at_one():
    rng = np.random.default_rng(0)
    scores = rng.normal(size=200)
    labels = (rng.random(200) < 0.2).astype(float)
    budget, recall = gain_curve(scores, labels)
    assert np.all(np.diff(budget) >= 0)
    assert np.all(np.diff(recall) >= 0)
    assert recall[-1] == pytest.approx(1.0)
    assert budget[-1] == pytest.approx(1.0)


def test_augc_ranks_a_good_model_above_a_random_one():
    rng = np.random.default_rng(1)
    labels = (rng.random(500) < 0.1).astype(float)
    informed = labels + rng.normal(scale=0.3, size=500)
    noise = rng.normal(size=500)
    assert augc(informed, labels) > augc(noise, labels)


def test_gain_curve_requires_a_positive_label():
    with pytest.raises(ValueError, match="at least one positive"):
        gain_curve([1.0, 2.0], [0, 0])


def test_prevalence_is_the_weighted_positive_rate():
    assert prevalence([1, 0, 0, 0]) == pytest.approx(0.25)
    assert prevalence([1, 0], weights=[3.0, 1.0]) == pytest.approx(0.75)
