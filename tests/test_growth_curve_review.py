"""Adversarial checks for fold-specific empirical height ceilings."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.growth_curve import blocked_predictions


def _settings(heights=None):
    return {
        "folds": 5,
        "seed": 42,
        "min_fit_cells": 20,
        "k_bounds": [0.000001, 1.0],
        "c_bounds": [1.01, 10.0],
        "initial_k": 0.03,
        "initial_c": 2.0,
        "soft_l1_scale_m": 1.0,
        "max_nfev": 200,
        "max_height_m": heights or {"oak": 10.0},
        "record_tree_height_m": {},
        "training_height_quantile": 0.995,
    }


@pytest.fixture
def oak_cells():
    blocks = np.repeat(np.arange(10), 20)
    start = np.linspace(7.0, 12.0, len(blocks))
    end = start + 2.0
    frame = pd.DataFrame(
        {
            "x": blocks * 1000.0,
            "y": np.zeros(len(blocks)),
            "model_group": ["oak"] * len(blocks),
            "broader_group": ["hardwood forest"] * len(blocks),
            "vegetation_type": ["oak"] * len(blocks),
        }
    )
    return frame, start, end, _settings()


def _predict(cells, *, start=None, end=None):
    frame, initial, target, settings = cells
    return blocked_predictions(
        frame,
        initial if start is None else start,
        target if end is None else end,
        8.96,
        1000,
        settings,
        a_mode="posthoc",
    )


def test_empirical_a_is_not_vacuously_pinned_to_literature(oak_cells):
    predicted = _predict(oak_cells)
    assert np.all(predicted["A"] > oak_cells[3]["max_height_m"]["oak"])


def test_held_out_target_heights_cannot_set_their_own_fold_a(oak_cells):
    original = _predict(oak_cells)
    held_out = original["folds"] == 0
    assert held_out.any()
    changed_end = oak_cells[2].copy()
    changed_end[held_out] += 100.0
    changed = _predict(oak_cells, end=changed_end)
    np.testing.assert_array_equal(changed["A"][held_out], original["A"][held_out])
    np.testing.assert_allclose(changed["curve"][held_out], original["curve"][held_out])
    np.testing.assert_allclose(
        changed["median"][held_out], original["median"][held_out]
    )


def test_training_target_heights_do_change_held_out_a(oak_cells):
    original = _predict(oak_cells)
    held_out = original["folds"] == 0
    changed_end = oak_cells[2].copy()
    changed_end[~held_out] += 5.0
    changed = _predict(oak_cells, end=changed_end)
    assert np.all(changed["A"][held_out] > original["A"][held_out])


def test_held_out_start_heights_change_prediction_but_not_a(oak_cells):
    original = _predict(oak_cells)
    held_out = original["folds"] == 0
    changed_start = oak_cells[1].copy()
    changed_start[held_out] += 1.0
    changed = _predict(oak_cells, start=changed_start)
    np.testing.assert_array_equal(changed["A"][held_out], original["A"][held_out])
    assert np.all(changed["curve"][held_out] > original["curve"][held_out])


def test_pooled_classes_keep_distinct_a_without_held_out_target_leak(oak_cells):
    frame, start, end, settings = oak_cells
    frame = frame.copy()
    names = np.tile(np.repeat(["oak", "pine"], 10), 10)
    frame["model_group"] = "group:forest"
    frame["broader_group"] = "forest"
    frame["vegetation_type"] = names
    settings = {**settings, "max_height_m": {"oak": 10.0, "pine": 40.0}}
    cells = frame, start, end, settings
    original = _predict(cells)
    held_out = original["folds"] == 0
    assert np.all(original["A"][held_out & (names == "pine")] == 40.0)
    assert np.all(original["A"][held_out & (names == "oak")] < 40.0)
    changed_end = end.copy()
    changed_end[held_out] += 100.0
    changed = _predict(cells, end=changed_end)
    np.testing.assert_array_equal(changed["A"][held_out], original["A"][held_out])


def test_absent_training_class_uses_literature_without_target_leak(oak_cells):
    frame, start, end, settings = oak_cells
    frame = frame.copy()
    frame["model_group"] = "group:forest"
    frame["broader_group"] = "forest"
    names = np.array(["pine"] * 20 + ["oak"] * (len(frame) - 20))
    frame["vegetation_type"] = names
    settings = {**settings, "max_height_m": {"oak": 10.0, "pine": 40.0}}
    cells = frame, start, end, settings
    original = _predict(cells)
    pine = names == "pine"
    assert np.all(original["literature_fallback"][pine])
    assert np.all(original["A"][pine] == 40.0)
    changed_end = end.copy()
    changed_end[pine] += 100.0
    changed = _predict(cells, end=changed_end)
    np.testing.assert_array_equal(changed["A"][pine], original["A"][pine])
    np.testing.assert_allclose(changed["curve"][pine], original["curve"][pine])
