"""Offline synthetic tests for the growth-curve gate."""

import numpy as np
import pandas as pd
import pytest

from canopyguard.forecasting.growth_curve import (
    block_mae_interval,
    blocked_predictions,
    chapman_richards,
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
    fit = fit_growth_curve(
        start, end, 8.96, settings(), maximum_start_height=float(start.max())
    )
    fitted = chapman_richards(start, 8.96, fit["A"], fit["k"], fit["c"])
    assert np.mean(np.abs(fitted - end)) < 0.1
    assert fit["A"] > end.max()
    assert fit["k"] > 0
    assert fit["c"] > 1
    gains = chapman_richards(
        np.array([5.0, 30.0]), 8.96, fit["A"], fit["k"], fit["c"]
    ) - np.array([5.0, 30.0])
    assert gains[0] > gains[1] > 0


def test_height_above_asymptote_ceiling_fails_closed():
    cfg = settings()
    cfg["a_upper_m"] = 20.0
    start = np.linspace(5, 30, 200)
    with pytest.raises(ValueError, match="ceiling"):
        fit_growth_curve(start, start + 1, 8.96, cfg, maximum_start_height=30)
