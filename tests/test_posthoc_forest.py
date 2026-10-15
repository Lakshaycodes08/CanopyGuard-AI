"""Post hoc analyses keep quality rules and refit each spatial training fold."""

import numpy as np
import pandas as pd

from canopyguard.evaluation.posthoc_forest import (
    all_forest_mask,
    score_forest,
    score_objective_mismatch,
)


def test_all_forest_keeps_disturbed_cells_but_excludes_bad_labels_and_wires():
    table = pd.DataFrame(
        {
            "vegetation_type": ["oak"] * 4,
            "broader_group": ["hardwood forest"] * 4,
            "overlap_disputed": [False, False, True, False],
            "label_change_valid": [True] * 4,
            "canopy_at_start": [True] * 4,
            "vegetation_known": [True] * 4,
            "hansen_valid": [True] * 4,
            "near_line": [False] * 4,
            "p95_wire_excluded": [False, False, False, True],
            "burned_2013_2022": [False, True, False, False],
            "hansen_loss": [False, True, False, False],
            "lidar_loss": [False, True, False, False],
        }
    )
    settings = {"excluded_map_classes": [], "forest_groups": ["hardwood forest"]}
    assert all_forest_mask(table, settings).tolist() == [True, True, False, False]


def test_posthoc_scores_use_finite_out_of_fold_predictions():
    frame = pd.DataFrame(
        {
            "x": [5.0, 15.0, 25.0, 35.0, 45.0, 55.0],
            "y": [5.0] * 6,
            "model_group": ["oak"] * 6,
            "broader_group": ["hardwood forest"] * 6,
        }
    )
    start = np.full(6, 10.0)
    end = start + np.array([0.0, 0.0, 1.0, 0.0, 1.0, 2.0])
    settings = {
        "folds": 2,
        "seed": 42,
        "min_fit_cells": 1,
        "bootstrap_draws": 100,
        "primary_block_m": 20,
    }
    score, (_, folds, median) = score_forest(frame, start, end, 20, settings)
    assert score["cells"] == 6
    assert score["blocks"] == 3
    assert len(np.unique(folds)) == 2
    assert np.isfinite(median).all()
    diagnostics = score_objective_mismatch(frame, start, end, settings)
    assert len(diagnostics["fold_mean_residual_offsets_m"]) == 2
    assert np.isfinite(diagnostics["intercept_only"]["candidate_mae_m"])
