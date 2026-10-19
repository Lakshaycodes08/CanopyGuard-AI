import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.hazard_model import (
    auc_roc,
    disturbance_labels,
    group_rate,
)


def test_auc_is_one_for_perfect_ranking_and_half_for_ties():
    label = np.array([0, 0, 1, 1], dtype=bool)
    assert auc_roc(np.array([0.1, 0.2, 0.8, 0.9]), label) == pytest.approx(1.0)
    assert auc_roc(np.zeros(4), label) == pytest.approx(0.5)
    assert auc_roc(np.array([0.9, 0.8, 0.2, 0.1]), label) == pytest.approx(0.0)


def test_auc_needs_both_classes():
    with pytest.raises(ValueError):
        auc_roc(np.array([0.1, 0.2]), np.array([True, True]))


def test_labels_use_the_configured_columns_and_thresholds():
    table = pd.DataFrame({"loss_share": [0.1, 0.4], "burned": [0.0, 1.0]})
    rules = {
        "loss": {"column": "loss_share", "threshold": 0.3},
        "burned": {"column": "burned", "threshold": 0.5},
    }
    labels = disturbance_labels(table, rules)
    assert labels["loss"].tolist() == [False, True]
    assert labels["burned"].tolist() == [False, True]


def test_group_rate_uses_only_other_folds_and_falls_back_to_overall():
    keys = pd.Series(["a", "a", "b", "c"])
    label = np.array([1, 0, 1, 1], dtype=bool)
    folds = np.array([0, 1, 1, 1])
    rate = group_rate(keys, label, folds)
    assert rate[0] == pytest.approx(0.0)
    assert rate[1] == pytest.approx(1.0)
    assert rate[2] == pytest.approx(1.0)
    assert rate[3] == pytest.approx(1.0)
