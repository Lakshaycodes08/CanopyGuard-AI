import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.growth_model import out_of_fold_predictions
from canopyguard.forecasting.reserved_test import (
    stack_train_test,
    stretch_predictions,
    years_between,
)

EPOCHS = [
    {"name": "2013", "start": "2013-09-28", "end": "2013-11-26"},
    {"name": "2022", "start": "2022-09-13", "end": "2022-11-11"},
    {"name": "2023", "start": "2023-09-16", "end": "2023-12-15"},
]


def test_interval_ratio_follows_the_survey_midpoints():
    first = years_between(EPOCHS, ("2013", "2022"))
    second = years_between(EPOCHS, ("2013", "2023"))
    assert first == pytest.approx(8.958, abs=0.001)
    assert second == pytest.approx(10.010, abs=0.001)
    assert second / first == pytest.approx(1.117, abs=0.001)


def test_stretching_scales_growth_but_not_the_no_change_guess():
    predictions = {"zero": np.zeros(2), "model": np.array([1.0, 2.0])}
    out = stretch_predictions(predictions, 1.5)
    assert out["zero"].tolist() == [0.0, 0.0]
    assert out["model"].tolist() == [1.5, 3.0]


def test_test_predictions_do_not_depend_on_the_test_labels():
    generator = np.random.default_rng(1)
    train = pd.DataFrame(
        {"f": generator.normal(size=80), "mean_change": generator.normal(size=80)}
    )
    test = pd.DataFrame(
        {"f": generator.normal(size=30), "mean_change": generator.normal(size=30)}
    )
    params = {"n_estimators": 20, "min_child_samples": 5, "num_leaves": 4}

    def predict(test_labels):
        shifted = test.assign(mean_change=test_labels)
        table, folds = stack_train_test(train, shifted)
        out = out_of_fold_predictions(table, ["f"], "mean_change", folds, params, 7)
        return out["model"][folds == 1], out["train_mean"][folds == 1]

    first_model, first_mean = predict(test["mean_change"].to_numpy())
    second_model, second_mean = predict(test["mean_change"].to_numpy() + 100.0)
    assert np.allclose(first_model, second_model)
    assert np.allclose(first_mean, second_mean)
