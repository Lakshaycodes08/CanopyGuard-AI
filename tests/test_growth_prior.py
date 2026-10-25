"""Offline tests for the type-specific growth prior and co-primary gate."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.evaluation.growth_gate import median_gate_decision
from canopyguard.forecasting.growth_prior import (
    fit_full_sample_type_median_prior,
    predict_type_median_prior,
)


def test_type_median_prior_pools_sparse_class_without_losing_class_mapping():
    names = ["oak"] * 4 + ["maple"] * 2
    frame = pd.DataFrame(
        {
            "vegetation_type": names,
            "model_group": names,
            "broader_group": ["hardwood forest"] * len(names),
        }
    )
    start = np.full(len(names), 10.0)
    end = start + np.array([1, 2, 3, 4, 10, 12])
    prior = fit_full_sample_type_median_prior(frame, start, end, minimum=3)
    assert prior["oak"]["fit_scope"] == "type:oak"
    assert prior["oak"]["median_increment_m"] == 2.5
    assert prior["maple"]["fit_scope"] == "broad:hardwood forest"
    assert prior["maple"]["median_increment_m"] == 3.5
    np.testing.assert_array_equal(
        predict_type_median_prior(["oak", "maple"], [10, 20], prior),
        [12.5, 23.5],
    )
    with pytest.raises(ValueError, match="No growth prior"):
        predict_type_median_prior(["unknown"], [10], prior)


def test_full_sample_prior_requires_one_model_group_per_map_class():
    frame = pd.DataFrame(
        {
            "vegetation_type": ["oak", "oak"],
            "model_group": ["oak", "group:hardwood forest"],
            "broader_group": ["hardwood forest", "hardwood forest"],
        }
    )
    with pytest.raises(ValueError, match="Multiple model groups"):
        fit_full_sample_type_median_prior(frame, [10, 10], [11, 12], minimum=1)


def test_median_gate_requires_both_forest_screens_to_beat_no_change():
    screens = {
        "forest_loss_on": {"median_minus_no_change": {"ci_high_m": -0.2}},
        "forest_loss_off": {"median_minus_no_change": {"ci_high_m": -0.1}},
    }
    assert median_gate_decision(screens) == "PASS"
    screens["forest_loss_off"]["median_minus_no_change"]["ci_high_m"] = 0.01
    assert median_gate_decision(screens) == "FAIL"
