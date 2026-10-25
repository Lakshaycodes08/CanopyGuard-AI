"""Stage-two fold isolation and fixed-model checks on small synthetic cells."""

import numpy as np
import pandas as pd

from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.evaluation.stage2_gate import _fold_predictions, score_screen


def fixture():
    block = np.repeat(np.arange(10), 20)
    start = 4.0 + block * 0.1 + np.tile(np.arange(20), 10) * 0.02
    end = start + 0.3 + 0.08 * block + 0.01 * start
    frame = pd.DataFrame(
        {
            "x": block * 1000.0,
            "y": np.zeros(len(block)),
            "model_group": ["oak"] * len(block),
            "broader_group": ["hardwood forest"] * len(block),
            "vegetation_type": ["oak"] * len(block),
            "mean_start": start * 0.8,
            "p95_start": start,
            "max_start": start * 1.2,
            "elevation_m": block.astype(float),
            "slope_deg": np.full(len(block), 8.0),
            "heat_load": np.full(len(block), 0.7),
            "tpi_450": np.zeros(len(block)),
        }
    )
    stage1 = {"folds": 5, "seed": 42, "min_fit_cells": 20, "bootstrap_draws": 20}
    settings = {
        "numeric_features": [
            "mean_start",
            "p95_start",
            "max_start",
            "elevation_m",
            "slope_deg",
            "heat_load",
            "tpi_450",
        ],
        "categorical_features": ["vegetation_type"],
        "ridge": {"alpha": 1.0},
        "lightgbm": {
            "objective": "regression",
            "max_depth": 4,
            "num_leaves": 15,
            "n_estimators": 400,
            "learning_rate": 0.03,
            "min_data_in_leaf": 200,
            "feature_fraction": 0.6,
            "deterministic": True,
            "force_col_wise": True,
            "n_jobs": 4,
            "verbosity": -1,
        },
    }
    return frame, start, end, stage1, settings


def test_held_out_target_cannot_change_its_fold_fit():
    frame, start, end, stage1, settings = fixture()
    blocks = assign_blocks(frame["x"], frame["y"], 1000)
    base, _, _, folds = _fold_predictions(
        frame, start, end, blocks, settings, stage1, ("ridge",)
    )
    for fold in range(stage1["folds"]):
        held_out = folds == fold
        altered = end.copy()
        altered[held_out] += 100
        changed, _, _, _ = _fold_predictions(
            frame, start, altered, blocks, settings, stage1, ("ridge",)
        )
        for name in ("stage1", "ridge"):
            np.testing.assert_allclose(changed[name][held_out], base[name][held_out])


def test_training_target_moves_held_out_prediction():
    frame, start, end, stage1, settings = fixture()
    blocks = assign_blocks(frame["x"], frame["y"], 1000)
    base, _, _, folds = _fold_predictions(
        frame, start, end, blocks, settings, stage1, ("ridge",)
    )
    held_out = folds == 0
    altered = end.copy()
    altered[~held_out] += 2
    changed, _, _, _ = _fold_predictions(
        frame, start, altered, blocks, settings, stage1, ("ridge",)
    )
    assert not np.allclose(changed["stage1"][held_out], base["stage1"][held_out])
    assert not np.allclose(changed["ridge"][held_out], base["ridge"][held_out])


def test_both_models_score_on_identical_cells():
    frame, start, end, stage1, settings = fixture()
    score, predictions, weights, folds = score_screen(
        frame, start, end, 1000, stage1, settings
    )
    assert score["cells"] == len(frame)
    assert score["blocks"] == 10
    assert len(np.unique(folds)) == 5
    assert all(np.isfinite(value).all() for value in predictions.values())
    assert weights["ridge"] and weights["lightgbm"]
