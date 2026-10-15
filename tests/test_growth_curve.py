"""Offline synthetic tests for the growth-curve gate."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.growth_curve import (
    block_mae_interval,
    blocked_predictions,
    chapman_richards,
    class_heights,
    fit_growth_curve,
)


def settings() -> dict:
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
        "max_height_m": {"oak": 70.0},
        "record_tree_height_m": {"oak": 90.0},
        "training_height_quantile": 0.995,
    }


def test_known_curve_beats_no_change_on_unseen_spatial_blocks():
    generator = np.random.default_rng(7)
    block_x, block_y = np.meshgrid(np.arange(10), np.arange(10))
    x = np.repeat(block_x.ravel() * 500.0, 10) + generator.uniform(0, 20, 1000)
    y = np.repeat(block_y.ravel() * 500.0, 10) + generator.uniform(0, 20, 1000)
    start = generator.uniform(2, 30, len(x))
    truth = chapman_richards(start, 8.96, 70.0, 0.04, 2.0)
    end = truth + generator.normal(0, 0.1, len(x))
    frame = pd.DataFrame(
        {
            "x": x,
            "y": y,
            "model_group": ["oak"] * len(x),
            "broader_group": ["hardwood forest"] * len(x),
            "vegetation_type": ["oak"] * len(x),
        }
    )
    predictions = blocked_predictions(frame, start, end, 8.96, 1000, settings())
    curve_error = predictions["curve"] - end
    zero_error = start - end
    interval = block_mae_interval(
        curve_error, zero_error, predictions["blocks"], draws=2000, seed=42
    )
    assert np.mean(np.abs(curve_error)) < 0.2
    assert interval["ci_high_m"] < 0
    for block in np.unique(predictions["blocks"]):
        assert np.unique(predictions["folds"][predictions["blocks"] == block]).size == 1


def test_fit_is_bounded_and_short_trees_gain_more():
    start = np.linspace(2, 40, 600)
    end = chapman_richards(start, 8.96, 70.0, 0.04, 2.0)
    fit = fit_growth_curve(start, end, 8.96, settings(), max_height_m=70.0)
    fitted = chapman_richards(start, 8.96, fit["A"], fit["k"], fit["c"])
    assert np.mean(np.abs(fitted - end)) < 0.1
    assert fit["A"] == 70.0
    assert fit["k"] > 0
    assert fit["c"] > 1
    gains = chapman_richards(
        np.array([5.0, 30.0]), 8.96, fit["A"], fit["k"], fit["c"]
    ) - np.array([5.0, 30.0])
    assert gains[0] > gains[1] > 0


def test_height_at_or_above_fixed_ceiling_has_no_predicted_growth():
    start = np.array([10.0, 20.0, 70.0, 80.0])
    predicted = chapman_richards(start, 8.96, 70.0, 0.04, 2.0)
    assert predicted[0] > start[0]
    assert predicted[-2:].tolist() == [70.0, 80.0]


def test_pooled_fit_keeps_class_specific_height_ceilings():
    cfg = settings()
    cfg["max_height_m"]["pine"] = 100.0
    names = np.array(["oak", "pine"])
    start = np.array([10.0, 10.0])
    end = np.array([12.0, 12.0])
    assert class_heights(names, start, end, cfg, "literature") == {
        "oak": 70.0,
        "pine": 100.0,
    }
    assert class_heights(names, start, end, cfg, "record")["oak"] == 90.0
    with pytest.raises(ValueError, match="Unconfirmed"):
        class_heights(np.array(["oak", "eucalyptus"]), start, end, cfg, "literature")


def test_posthoc_a_uses_training_pair_max_and_literature_floor():
    cfg = settings()
    cfg["max_height_m"] = {"oak": 20.0, "pine": 60.0}
    names = np.array(["oak", "oak", "pine", "pine"])
    start = np.array([15.0, 21.0, 12.0, 14.0])
    end = np.array([27.0, 23.0, 18.0, 20.0])
    heights = class_heights(names, start, end, cfg, "posthoc")
    assert heights["oak"] == pytest.approx(26.98)
    assert heights["pine"] == 60.0


def test_held_out_2022_heights_cannot_change_fold_a_or_prediction():
    generator = np.random.default_rng(19)
    cfg = settings()
    cfg["max_height_m"] = {"oak": 10.0}
    block = np.repeat(np.arange(20), 25)
    start = generator.uniform(5.0, 15.0, len(block))
    end = start + generator.uniform(1.0, 5.0, len(block))
    frame = pd.DataFrame(
        {
            "x": block * 1000.0,
            "y": np.zeros(len(block)),
            "model_group": ["oak"] * len(block),
            "broader_group": ["hardwood forest"] * len(block),
            "vegetation_type": ["oak"] * len(block),
        }
    )
    original = blocked_predictions(frame, start, end, 8.96, 1000, cfg, a_mode="posthoc")
    held_out = original["folds"] == 0
    altered_end = end.copy()
    altered_end[held_out] += 500.0
    changed = blocked_predictions(
        frame, start, altered_end, 8.96, 1000, cfg, a_mode="posthoc"
    )
    np.testing.assert_array_equal(changed["A"][held_out], original["A"][held_out])
    np.testing.assert_allclose(changed["curve"][held_out], original["curve"][held_out])


def test_spatially_isolated_class_uses_literature_a_without_held_out_leak():
    cfg = settings()
    cfg["min_fit_cells"] = 20
    cfg["max_height_m"] = {"oak": 40.0, "pine": 60.0}
    block = np.repeat(np.arange(10), 20)
    names = np.where(block == 0, "pine", "oak")
    start = np.full(len(block), 10.0)
    end = np.full(len(block), 14.0)
    frame = pd.DataFrame(
        {
            "x": block * 1000.0,
            "y": np.zeros(len(block)),
            "model_group": ["group:forest"] * len(block),
            "broader_group": ["forest"] * len(block),
            "vegetation_type": names,
        }
    )
    original = blocked_predictions(frame, start, end, 8.96, 1000, cfg, a_mode="posthoc")
    isolated = names == "pine"
    assert original["literature_fallback"].sum() == isolated.sum()
    np.testing.assert_array_equal(original["A"][isolated], 60.0)
    changed_end = end.copy()
    changed_end[isolated] = 500.0
    changed = blocked_predictions(
        frame, start, changed_end, 8.96, 1000, cfg, a_mode="posthoc"
    )
    np.testing.assert_array_equal(changed["A"][isolated], original["A"][isolated])
    np.testing.assert_allclose(changed["curve"][isolated], original["curve"][isolated])


def test_pooled_predictions_use_each_class_height_ceiling():
    generator = np.random.default_rng(11)
    cfg = settings()
    cfg["max_height_m"] = {"oak": 20.0, "pine": 60.0}
    block = np.repeat(np.arange(20), 50)
    names = np.tile(np.repeat(["oak", "pine"], 25), 20)
    start = generator.uniform(7.0, 17.0, len(block))
    ceilings = np.array([cfg["max_height_m"][name] for name in names])
    end = chapman_richards(start, 8.96, ceilings, 0.04, 2.0)
    frame = pd.DataFrame(
        {
            "x": block * 1000.0,
            "y": np.zeros(len(block)),
            "model_group": ["group:forest"] * len(block),
            "broader_group": ["forest"] * len(block),
            "vegetation_type": names,
        }
    )
    predicted = blocked_predictions(frame, start, end, 8.96, 1000, cfg)
    assert np.mean(np.abs(predicted["curve"] - end)) < 0.1
