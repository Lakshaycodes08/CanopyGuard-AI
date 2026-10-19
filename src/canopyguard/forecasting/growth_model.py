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
    "burned",
}


def feature_columns(
    table: pd.DataFrame, prefixes: list[str] | None = None
) -> list[str]:
    """Predictor columns, never a LiDAR column; optionally by name prefix."""
    names = [name for name in table.columns if name not in NON_FEATURES]
    if prefixes is None:
        return names
    return [name for name in names if name.startswith(tuple(prefixes))]


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


def dominant_class(table: pd.DataFrame, prefix: str = "eco_") -> NDArray:
    """Mapped class covering most of each row; 'none' outside the map."""
    columns = [name for name in table.columns if name.startswith(prefix)]
    shares = table[columns].to_numpy(dtype=np.float64)
    missing = np.isnan(shares).all(axis=1)
    best = np.argmax(np.where(np.isnan(shares), -1.0, shares), axis=1)
    labels = np.array(columns, dtype=object)[best]
    labels[missing] = "none"
    return labels


def group_median_predictions(
    keys: pd.Series, target: NDArray, folds: NDArray[np.int64]
) -> NDArray[np.float64]:
    """Training-fold median change per group; global median if group unseen."""
    pred = np.full(len(keys), np.nan)
    frame = pd.DataFrame({"key": keys.to_numpy(), "y": target})
    for fold in np.unique(folds):
        test = folds == fold
        train = frame[~test]
        medians = train.groupby("key")["y"].median()
        pred[test] = frame.loc[test, "key"].map(medians).fillna(train["y"].median())
    return pred


def survey_comparators(
    table: pd.DataFrame,
    target: str,
    folds: NDArray[np.int64],
    height_edges: list[float],
) -> dict[str, NDArray[np.float64]]:
    """Predictions that use the 2013 airborne survey height. Comparison only.

    These show what is achievable when a survey exists, so the satellite-only
    model can be read against them. They are never inputs to that model.
    """
    y = table[target].to_numpy(dtype=np.float64)
    height_bin = pd.cut(table["p95_start"], height_edges, right=False).astype(str)
    eco = pd.Series(dominant_class(table), index=table.index)
    return {
        "eco_class_median": group_median_predictions(eco, y, folds),
        "survey_height_median": group_median_predictions(height_bin, y, folds),
        "survey_height_x_eco_median": group_median_predictions(
            eco + "|" + height_bin, y, folds
        ),
    }


def columns_with_survey(table: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    """All satellite and site columns plus 2013 survey height, for comparison."""
    prefixes = sorted({p for v in config["model"]["feature_sets"].values() for p in v})
    return feature_columns(table, prefixes) + ["p95_start", "mean_start"]


def all_predictions(
    table: pd.DataFrame,
    config: dict[str, Any],
    folds: NDArray[np.int64],
    height_edges: list[float],
) -> dict[str, NDArray[np.float64]]:
    """Held-out predictions for every model, baseline and survey comparator."""
    target = config["model"]["target"]
    params = config["model"]["lightgbm"]
    seed = int(config["seed"])
    predictions: dict[str, NDArray[np.float64]] = {}
    for name, prefixes in config["model"]["feature_sets"].items():
        columns = feature_columns(table, prefixes)
        held_out = out_of_fold_predictions(table, columns, target, folds, params, seed)
        predictions[name] = held_out["model"]
        predictions["zero"] = held_out["zero"]
        predictions["train_mean"] = held_out["train_mean"]
    predictions.update(survey_comparators(table, target, folds, height_edges))
    with_survey = columns_with_survey(table, config)
    predictions["lightgbm_satellite_plus_survey"] = out_of_fold_predictions(
        table, with_survey, target, folds, params, seed
    )["model"]
    return predictions


def paired_error_vectors(
    y: NDArray, predictions: dict[str, NDArray], first: str, second: str
) -> tuple[NDArray, NDArray]:
    """Signed errors of two models on the same rows."""
    return y - predictions[first], y - predictions[second]
