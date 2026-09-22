"""Regression and budget-constrained ranking metrics."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _paired(y_true: ArrayLike, y_pred: ArrayLike) -> tuple[NDArray, NDArray]:
    truth = np.asarray(y_true, dtype=np.float64).ravel()
    prediction = np.asarray(y_pred, dtype=np.float64).ravel()
    if truth.shape != prediction.shape:
        raise ValueError("Truth and prediction must have the same shape")
    if truth.size == 0:
        raise ValueError("Metric inputs must be non-empty")
    return truth, prediction


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean absolute error."""
    truth, prediction = _paired(y_true, y_pred)
    return float(np.mean(np.abs(truth - prediction)))


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Root mean squared error."""
    truth, prediction = _paired(y_true, y_pred)
    return float(np.sqrt(np.mean((truth - prediction) ** 2)))


def bias(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Signed mean error, prediction minus truth."""
    truth, prediction = _paired(y_true, y_pred)
    return float(np.mean(prediction - truth))


def r2(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Coefficient of determination against the truth mean."""
    truth, prediction = _paired(y_true, y_pred)
    total = float(np.sum((truth - np.mean(truth)) ** 2))
    if total == 0.0:
        raise ValueError("Cannot compute r2 when truth has zero variance")
    residual = float(np.sum((truth - prediction) ** 2))
    return 1.0 - residual / total


def average_ranks(values: ArrayLike) -> NDArray[np.float64]:
    """Return ranks with ties averaged, starting at one."""
    array = np.asarray(values, dtype=np.float64).ravel()
    order = np.argsort(array, kind="stable")
    ranks = np.empty(array.size, dtype=np.float64)
    ranks[order] = np.arange(1, array.size + 1, dtype=np.float64)
    sorted_values = array[order]
    start = 0
    for stop in range(1, array.size + 1):
        if stop == array.size or sorted_values[stop] != sorted_values[start]:
            ranks[order[start:stop]] = ranks[order[start:stop]].mean()
            start = stop
    return ranks


def spearman(left: ArrayLike, right: ArrayLike) -> float:
    """Spearman rank correlation without a SciPy dependency."""
    first, second = _paired(left, right)
    ranked_first = average_ranks(first)
    ranked_second = average_ranks(second)
    centred_first = ranked_first - ranked_first.mean()
    centred_second = ranked_second - ranked_second.mean()
    denominator = np.linalg.norm(centred_first) * np.linalg.norm(centred_second)
    if denominator == 0.0:
        raise ValueError("Cannot rank-correlate a constant sequence")
    return float(centred_first @ centred_second / denominator)


def _ranked_inputs(
    scores: ArrayLike, labels: ArrayLike, weights: ArrayLike | None
) -> tuple[NDArray, NDArray]:
    score = np.asarray(scores, dtype=np.float64).ravel()
    label = np.asarray(labels, dtype=np.float64).ravel()
    if score.shape != label.shape:
        raise ValueError("Scores and labels must have the same shape")
    if score.size == 0:
        raise ValueError("Ranking inputs must be non-empty")

    weight = (
        np.ones_like(score)
        if weights is None
        else np.asarray(weights, dtype=np.float64).ravel()
    )
    if weight.shape != score.shape:
        raise ValueError("Weights must match the score shape")
    if np.any(weight < 0):
        raise ValueError("Weights must be non-negative")

    order = np.argsort(-score, kind="stable")
    return label[order], weight[order]


def gain_curve(
    scores: ArrayLike, labels: ArrayLike, weights: ArrayLike | None = None
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return cumulative budget fraction and cumulative recall of positives."""
    label, weight = _ranked_inputs(scores, labels, weights)
    positives = float(np.sum(label))
    if positives <= 0:
        raise ValueError("Gain curve requires at least one positive label")

    budget = np.cumsum(weight) / float(np.sum(weight))
    recall = np.cumsum(label) / positives
    return budget, recall


def recall_at_k(
    scores: ArrayLike,
    labels: ArrayLike,
    k_fraction: float,
    weights: ArrayLike | None = None,
) -> float:
    """Recall of positives within the top k fraction of ranked weight."""
    if not 0.0 < k_fraction <= 1.0:
        raise ValueError("k_fraction must lie in (0, 1]")
    budget, recall = gain_curve(scores, labels, weights)
    selected = budget <= k_fraction
    return float(recall[selected][-1]) if selected.any() else 0.0


def precision_at_k(
    scores: ArrayLike,
    labels: ArrayLike,
    k_fraction: float,
    weights: ArrayLike | None = None,
) -> float:
    """Weighted precision within the top k fraction of ranked weight."""
    if not 0.0 < k_fraction <= 1.0:
        raise ValueError("k_fraction must lie in (0, 1]")
    label, weight = _ranked_inputs(scores, labels, weights)
    budget = np.cumsum(weight) / float(np.sum(weight))
    selected = budget <= k_fraction
    if not selected.any():
        return 0.0
    chosen_weight = float(np.sum(weight[selected]))
    if chosen_weight == 0.0:
        return 0.0
    return float(np.sum(label[selected] * weight[selected]) / chosen_weight)


def augc(
    scores: ArrayLike,
    labels: ArrayLike,
    max_fraction: float = 0.20,
    weights: ArrayLike | None = None,
) -> float:
    """Normalised partial area under the gain curve up to a budget fraction."""
    if not 0.0 < max_fraction <= 1.0:
        raise ValueError("max_fraction must lie in (0, 1]")
    budget, recall = gain_curve(scores, labels, weights)
    grid = np.linspace(0.0, max_fraction, 512)
    interpolated = np.interp(grid, budget, recall, left=0.0)
    return float(np.trapezoid(interpolated, grid) / max_fraction)


def prevalence(labels: ArrayLike, weights: ArrayLike | None = None) -> float:
    """Weighted positive rate, the no-skill floor for precision metrics."""
    label = np.asarray(labels, dtype=np.float64).ravel()
    weight = (
        np.ones_like(label)
        if weights is None
        else np.asarray(weights, dtype=np.float64).ravel()
    )
    total = float(np.sum(weight))
    if total == 0.0:
        raise ValueError("Weights must sum to a positive value")
    return float(np.sum(label * weight) / total)
