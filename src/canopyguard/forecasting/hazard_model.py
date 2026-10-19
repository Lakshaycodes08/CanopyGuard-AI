"""Rank pixels by the chance of later disturbance, from data before the cutoff.

This is a research prioritisation, not a clearance or safety determination.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from canopyguard.evaluation.metrics import average_ranks, recall_at_k


def disturbance_labels(
    table: pd.DataFrame, definitions: dict[str, dict[str, Any]]
) -> dict[str, NDArray[np.bool_]]:
    """Binary targets from label and fire columns; these are never predictors."""
    return {
        name: (table[rule["column"]] >= float(rule["threshold"])).to_numpy()
        for name, rule in definitions.items()
    }


def auc_roc(score: NDArray, label: NDArray) -> float:
    """Chance a random positive outranks a random negative (ties count half)."""
    positive = np.asarray(label, dtype=bool)
    count = int(positive.sum())
    other = positive.size - count
    if count == 0 or other == 0:
        raise ValueError("AUC needs both classes")
    ranks = average_ranks(np.asarray(score, dtype=np.float64))
    return float((ranks[positive].sum() - count * (count + 1) / 2) / (count * other))


def held_out_probability(
    table: pd.DataFrame,
    columns: list[str],
    label: NDArray[np.bool_],
    folds: NDArray[np.int64],
    params: dict[str, Any],
    seed: int,
) -> NDArray[np.float64]:
    """Out-of-fold probability from a LightGBM classifier, one fold at a time."""
    import lightgbm as lgb

    probability = np.full(len(table), np.nan)
    settings = {**params, "objective": "binary"}
    for fold in np.unique(folds):
        test = folds == fold
        model = lgb.LGBMClassifier(**settings, random_state=seed, n_jobs=-1, verbose=-1)
        model.fit(table.loc[~test, columns], label[~test])
        probability[test] = model.predict_proba(table.loc[test, columns])[:, 1]
    return probability


def group_rate(
    keys: pd.Series, label: NDArray[np.bool_], folds: NDArray[np.int64]
) -> NDArray[np.float64]:
    """Training-fold event rate per group; overall rate if the group is unseen."""
    frame = pd.DataFrame({"key": keys.to_numpy(), "y": label.astype(float)})
    rate = np.full(len(frame), np.nan)
    for fold in np.unique(folds):
        test = folds == fold
        train = frame[~test]
        by_group = train.groupby("key")["y"].mean()
        rate[test] = frame.loc[test, "key"].map(by_group).fillna(train["y"].mean())
    return rate


def ranking_scores(
    score: NDArray, label: NDArray[np.bool_], k_fractions: list[float]
) -> dict[str, float]:
    """AUC, recall within the top share of pixels, and the base rate."""
    result = {"auc": auc_roc(score, label), "base_rate": float(label.mean())}
    for k in k_fractions:
        result[f"recall_at_{int(k * 100)}pct"] = recall_at_k(
            score, label.astype(float), k
        )
    return result
