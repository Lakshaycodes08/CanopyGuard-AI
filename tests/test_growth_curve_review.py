"""AI reviewer leakage checks for the post hoc growth-curve A rule.

Added by the A-rule spot-check recorded in configs/forecasting.yaml under
growth_curve.reviewer_spot_check_followup. These checks are deliberately adversarial.
test_training_2022_heights_must_move_fold_a guards the other tests: if the
perturbation path ever goes dead, the inertness assertions would pass
vacuously and prove nothing about leakage.
"""

import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.growth_curve import blocked_predictions, class_heights

DT_YEARS = 8.96
BLOCK_M = 1000.0


def settings() -> dict:
    """Synthetic single-class configuration with a low literature A floor."""
    return {
        "folds": 5,
        "seed": 42,
        "min_fit_cells": 100,
        "a_margin_m": 0.01,
        "a_upper_m": 120.0,
        "a_upper_warning_fraction": 0.99,
        "k_bounds": [0.000001, 1.0],
        "c_bounds": [1.01, 10.0],
        "initial_k": 0.03,
        "initial_c": 2.0,
        "soft_l1_scale_m": 1.0,
        "max_nfev": 200,
        "max_height_m": {"oak": 10.0},
        "record_tree_height_m": {"oak": 90.0},
        "training_height_quantile": 0.995,
    }


def one_class_frame(blocks: int = 20, per_block: int = 25, seed: int = 19):
    """One mapped class spread over distinct spatial blocks."""
    generator = np.random.default_rng(seed)
    block = np.repeat(np.arange(blocks), per_block)
    start = generator.uniform(5.0, 15.0, len(block))
    end = start + generator.uniform(1.0, 5.0, len(block))
    frame = pd.DataFrame(
        {
            "x": block * BLOCK_M,
            "y": np.zeros(len(block)),
            "model_group": ["oak"] * len(block),
            "broader_group": ["hardwood forest"] * len(block),
            "vegetation_type": ["oak"] * len(block),
        }
    )
    return frame, start, end


def predict(frame, start, end, config) -> dict:
    return blocked_predictions(
        frame, start, end, DT_YEARS, BLOCK_M, config, a_mode="posthoc"
    )


def test_no_fold_reacts_to_its_own_held_out_2022_heights():
    """Every fold, not only fold zero, must ignore its own target epoch."""
    frame, start, end = one_class_frame()
    base = predict(frame, start, end, settings())
    for fold in range(settings()["folds"]):
        held_out = base["folds"] == fold
        assert held_out.any()
        altered = end.copy()
        altered[held_out] += 500.0
        changed = predict(frame, start, altered, settings())
        np.testing.assert_array_equal(changed["A"][held_out], base["A"][held_out])
        np.testing.assert_allclose(changed["curve"][held_out], base["curve"][held_out])
        np.testing.assert_allclose(
            changed["median"][held_out], base["median"][held_out]
        )


def test_training_2022_heights_must_move_fold_a():
    """Non-vacuity guard: training targets are what set a fold's A."""
    frame, start, end = one_class_frame()
    base = predict(frame, start, end, settings())
    held_out = base["folds"] == 0
    altered = end.copy()
    altered[~held_out] += 500.0
    changed = predict(frame, start, altered, settings())
    assert not np.array_equal(changed["A"][held_out], base["A"][held_out])


def test_held_out_start_height_changes_its_own_prediction():
    """The 2013 start height is a legitimate predictor and must be used."""
    frame, start, end = one_class_frame()
    base = predict(frame, start, end, settings())
    held_out = base["folds"] == 0
    altered = start.copy()
    altered[held_out] = np.clip(altered[held_out] * 0.5, 0.1, None)
    changed = predict(frame, altered, end, settings())
    assert not np.allclose(changed["curve"][held_out], base["curve"][held_out])


def test_one_held_out_cell_cannot_affect_another_in_the_same_fold():
    """No within-fold contamination between held-out cells."""
    frame, start, end = one_class_frame()
    base = predict(frame, start, end, settings())
    rows = np.flatnonzero(base["folds"] == 0)
    altered = end.copy()
    altered[rows[0]] += 1000.0
    changed = predict(frame, start, altered, settings())
    others = rows[1:]
    np.testing.assert_array_equal(changed["A"][others], base["A"][others])
    np.testing.assert_allclose(changed["curve"][others], base["curve"][others])


def test_class_heights_takes_literature_floor_or_training_quantile():
    """A equals max(literature upper, training p99.5 of max(start, end))."""
    config = settings()
    config["max_height_m"] = {"short": 20.0, "tall": 60.0}
    names = np.array(["short", "short", "short", "short", "tall", "tall"])
    start = np.array([15.0, 21.0, 10.0, 11.0, 12.0, 14.0])
    end = np.array([27.0, 23.0, 12.0, 13.0, 18.0, 20.0])
    heights = class_heights(names, start, end, config, "posthoc")
    paired = np.maximum(start, end)
    quantile = config["training_height_quantile"]
    expected = max(20.0, float(np.quantile(paired[names == "short"], quantile)))
    assert heights["short"] == pytest.approx(expected)
    assert heights["short"] > 20.0
    assert heights["tall"] == 60.0


def test_median_baseline_depends_on_training_rows_only():
    """The median increment ignores held-out targets and tracks training ones."""
    frame, start, end = one_class_frame()
    base = predict(frame, start, end, settings())
    held_out = base["folds"] == 0
    inert = end.copy()
    inert[held_out] += 500.0
    np.testing.assert_allclose(
        predict(frame, start, inert, settings())["median"][held_out],
        base["median"][held_out],
    )
    responsive = end.copy()
    responsive[~held_out] += 7.0
    assert not np.allclose(
        predict(frame, start, responsive, settings())["median"][held_out],
        base["median"][held_out],
    )
