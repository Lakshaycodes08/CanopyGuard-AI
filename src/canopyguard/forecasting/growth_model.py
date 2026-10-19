"""Spatially blocked evaluation of satellite-only canopy change models.

The risk or growth estimate is a research prioritisation, not a regulatory
clearance or safety certification.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from canopyguard.evaluation.blocks import assign_blocks, systematic_folds
from canopyguard.evaluation.metrics import bias, mae, r2, rmse

NON_FEATURES = {
    "block_row",
    "block_col",
    "n_cells",
    "n_pixels",
    "x",
    "y",
    "scale_pixels",
    "mean_change",
    "p95_change",
    "mean_start",
    "p95_start",
    "canopy_share",
    "loss_share",
}


def feature_columns(table: pd.DataFrame) -> list[str]:
    """Predictor columns: satellite history only, never a LiDAR column."""
    return [name for name in table.columns if name not in NON_FEATURES]


def spatial_folds(
    table: pd.DataFrame, block_size_m: float, n_folds: int, seed: int
) -> NDArray[np.int64]:
    """Fold per row, with whole blocks held out together."""
    blocks = assign_blocks(table["x"], table["y"], block_size_m)
    return systematic_folds(blocks, n_folds, seed)


def fit_lightgbm(
    features: pd.DataFrame, target: NDArray, params: dict[str, Any], seed: int
):
    import lightgbm as lgb

    model = lgb.LGBMRegressor(**params, random_state=seed, n_jobs=-1, verbose=-1)
    return model.fit(features, target)


def out_of_fold_predictions(
    table: pd.DataFrame,
    columns: list[str],
    target: str,
    folds: NDArray[np.int64],
    params: dict[str, Any],
    seed: int,
) -> dict[str, NDArray[np.float64]]:
    """Held-out predictions for the model and the training-mean baseline."""
    y = table[target].to_numpy(dtype=np.float64)
    model_pred = np.full(len(table), np.nan)
    mean_pred = np.full(len(table), np.nan)
    for fold in np.unique(folds):
        test = folds == fold
        train = ~test
        model = fit_lightgbm(table.loc[train, columns], y[train], params, seed)
        model_pred[test] = model.predict(table.loc[test, columns])
        mean_pred[test] = y[train].mean()
    return {"model": model_pred, "train_mean": mean_pred, "zero": np.zeros(len(y))}


def score(y: NDArray, pred: NDArray) -> dict[str, float]:
    return {
        "mae": mae(y, pred),
        "rmse": rmse(y, pred),
        "bias": bias(y, pred),
        "r2": r2(y, pred),
        "n": int(np.isfinite(y).sum()),
    }


def score_by_stratum(
    table: pd.DataFrame,
    target: str,
    predictions: dict[str, NDArray],
    edges: list[float],
) -> dict[str, dict[str, dict[str, float]]]:
    """Scores per 2013 canopy height class; start height is a grader only."""
    y = table[target].to_numpy()
    labels = pd.cut(table["p95_start"], edges, right=False).astype(str).to_numpy()
    out: dict[str, dict[str, dict[str, float]]] = {}
    for label in sorted(set(labels)):
        mask = labels == label
        if mask.sum() < 50:
            continue
        out[label] = {
            name: score(y[mask], pred[mask]) for name, pred in predictions.items()
        }
    return out
