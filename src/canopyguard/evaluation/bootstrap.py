"""Paired spatial block bootstrap for differences between two models."""

from __future__ import annotations

from collections.abc import Callable
from statistics import NormalDist

import numpy as np
from numpy.typing import ArrayLike, NDArray

Statistic = Callable[[NDArray[np.float64]], float]
_NORMAL = NormalDist()


def _block_index(block_ids: ArrayLike) -> tuple[NDArray, list[NDArray]]:
    ids = np.asarray(block_ids).ravel()
    unique = np.unique(ids)
    if unique.size < 2:
        raise ValueError("Block bootstrap requires at least two blocks")
    return unique, [np.flatnonzero(ids == value) for value in unique]


def _statistic_over(
    values: NDArray[np.float64], groups: list[NDArray], statistic: Statistic
) -> float:
    return statistic(np.concatenate([values[group] for group in groups]))


def _bca_interval(
    observed: float,
    replicates: NDArray[np.float64],
    jackknife: NDArray[np.float64],
    confidence_level: float,
) -> tuple[float, float]:
    """Bias-corrected and accelerated interval from block replicates."""
    below = float(np.mean(replicates < observed))
    if below <= 0.0 or below >= 1.0:
        alpha = (1.0 - confidence_level) / 2.0
        return (
            float(np.quantile(replicates, alpha)),
            float(np.quantile(replicates, 1.0 - alpha)),
        )

    bias_correction = _NORMAL.inv_cdf(below)
    centred = jackknife.mean() - jackknife
    denominator = 6.0 * float(np.sum(centred**2)) ** 1.5
    skew = float(np.sum(centred**3))
    acceleration = 0.0 if denominator == 0.0 else skew / denominator

    alpha = (1.0 - confidence_level) / 2.0
    bounds = []
    for tail in (alpha, 1.0 - alpha):
        z = bias_correction + _NORMAL.inv_cdf(tail)
        adjusted = bias_correction + z / (1.0 - acceleration * z)
        bounds.append(float(np.quantile(replicates, _NORMAL.cdf(adjusted))))
    return bounds[0], bounds[1]


def paired_block_bootstrap(
    errors_a: ArrayLike,
    errors_b: ArrayLike,
    block_ids: ArrayLike,
    *,
    statistic: Statistic | None = None,
    resamples: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap the paired statistic difference, resampling whole blocks.

    Blocks are the resampling unit because residuals inside a block are
    spatially correlated. Resampling cells would understate the interval.
    """
    first = np.asarray(errors_a, dtype=np.float64).ravel()
    second = np.asarray(errors_b, dtype=np.float64).ravel()
    if first.shape != second.shape:
        raise ValueError("Both error vectors must have the same shape")
    if resamples < 1:
        raise ValueError("Resample count must be positive")

    reduce: Statistic = statistic or (lambda values: float(np.mean(np.abs(values))))
    unique, groups = _block_index(block_ids)
    if first.size != np.asarray(block_ids).ravel().size:
        raise ValueError("Block identifiers must match the error vector length")

    def difference(selected: list[NDArray]) -> float:
        return _statistic_over(first, selected, reduce) - _statistic_over(
            second, selected, reduce
        )

    observed = difference(groups)
    generator = np.random.default_rng(seed)
    draws = generator.integers(0, len(groups), size=(resamples, len(groups)))
    replicates = np.array([difference([groups[i] for i in row]) for row in draws])
    jackknife = np.array(
        [
            difference([groups[i] for i in range(len(groups)) if i != leave_out])
            for leave_out in range(len(groups))
        ]
    )

    low, high = _bca_interval(observed, replicates, jackknife, confidence_level)
    return {
        "difference": observed,
        "ci_low": low,
        "ci_high": high,
        "p_value_ge_zero": float(np.mean(replicates >= 0.0)),
        "blocks": float(unique.size),
        "resamples": float(resamples),
    }


def excludes_zero(result: dict[str, float]) -> bool:
    """Return True when the bootstrap interval does not contain zero."""
    return result["ci_low"] > 0.0 or result["ci_high"] < 0.0
