"""Empirical noise floor and the change detectability surface."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

NMAD_SCALE = 1.4826
LOD95_Z = 1.96


def _finite(values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64).ravel()
    array = array[np.isfinite(array)]
    if array.size < 2:
        raise ValueError("At least two finite values are required")
    return array


def normalised_mad(values: ArrayLike) -> float:
    """Robust standard deviation estimate from the median absolute deviation."""
    array = _finite(values)
    return float(NMAD_SCALE * np.median(np.abs(array - np.median(array))))


def noise_sigma(delta: ArrayLike, robust: bool = True) -> float:
    """Measurement error standard deviation from a short-interval difference.

    The one-year repeat pair carries negligible true change relative to its
    error, so the spread of that difference estimates the error directly.
    """
    array = _finite(delta)
    return normalised_mad(array) if robust else float(np.std(array, ddof=1))


def lod95(sigma: float) -> float:
    """Ninety-five percent limit of detection for a single difference."""
    if sigma < 0:
        raise ValueError("Sigma must be non-negative")
    return float(LOD95_Z * sigma)


def decay_exponent(
    scales_m: ArrayLike, sigmas: ArrayLike, base_scale_m: float
) -> dict[str, float]:
    """Fit sigma against the cell count implied by each aggregation scale.

    The model is sigma = a * N ** -b. Spatially independent error gives
    b = 0.5. Correlated error gives b below 0.5.
    """
    scales = np.asarray(scales_m, dtype=np.float64).ravel()
    sigma = np.asarray(sigmas, dtype=np.float64).ravel()
    if scales.shape != sigma.shape:
        raise ValueError("Scales and sigmas must have the same shape")
    if scales.size < 3:
        raise ValueError("Decay fit requires at least three scales")
    if np.any(scales <= 0) or np.any(sigma <= 0) or base_scale_m <= 0:
        raise ValueError("Scales, sigmas, and the base scale must be positive")

    cells = (scales / base_scale_m) ** 2
    design = np.column_stack([np.ones_like(cells), -np.log(cells)])
    solution, *_ = np.linalg.lstsq(design, np.log(sigma), rcond=None)
    predicted = design @ solution
    residual = float(np.sum((np.log(sigma) - predicted) ** 2))
    total = float(np.sum((np.log(sigma) - np.mean(np.log(sigma))) ** 2))
    return {
        "coefficient": float(np.exp(solution[0])),
        "exponent": float(solution[1]),
        "r2": 1.0 - residual / total if total > 0 else float("nan"),
    }


def detectable_fraction(delta: ArrayLike, limit: float) -> float:
    """Share of cells whose absolute change exceeds the detection limit."""
    if limit < 0:
        raise ValueError("Detection limit must be non-negative")
    array = _finite(delta)
    return float(np.mean(np.abs(array) > limit))


def surface_row(
    delta: ArrayLike, sigma: float, scale_m: float, baseline_years: float
) -> dict[str, float]:
    """One cell of the detectability surface for a scale and baseline pair."""
    if baseline_years <= 0:
        raise ValueError("Temporal baseline must be positive")

    array = _finite(delta)
    limit = lod95(sigma)
    signal = float(np.median(np.abs(array)))
    return {
        "scale_m": float(scale_m),
        "baseline_years": float(baseline_years),
        "sigma_m": float(sigma),
        "lod95_m": limit,
        "signal_m": signal,
        "snr": signal / sigma if sigma > 0 else float("inf"),
        "annual_rate_m": signal / baseline_years,
        "detectable_fraction": detectable_fraction(array, limit),
        "cells": float(array.size),
    }


def minimum_detectable_baseline(sigma: float, annual_rate_m: float) -> float:
    """Years of growth needed for the accumulated change to clear LoD95."""
    if annual_rate_m <= 0:
        raise ValueError("Annual growth rate must be positive")
    return lod95(sigma) / annual_rate_m


def smallest_resolving_scale(
    rows: list[dict[str, float]], min_snr: float = 1.0
) -> float:
    """Smallest aggregation scale whose signal-to-noise reaches the threshold."""
    resolving = [row["scale_m"] for row in rows if row["snr"] >= min_snr]
    return float(min(resolving)) if resolving else float("nan")


def noise_floor_table(
    delta_by_scale: dict[float, ArrayLike], base_scale_m: float
) -> list[dict[str, float]]:
    """Measured error standard deviation and detection limit at each scale."""
    rows = []
    for scale in sorted(delta_by_scale):
        values = _finite(delta_by_scale[scale])
        sigma = noise_sigma(values, robust=True)
        rows.append(
            {
                "scale_m": float(scale),
                "cells": float(values.size),
                "mean_m": float(np.mean(values)),
                "sigma_m": sigma,
                "sigma_plain_m": noise_sigma(values, robust=False),
                "lod95_m": lod95(sigma),
            }
        )
    decay = decay_exponent(
        [row["scale_m"] for row in rows],
        [row["sigma_m"] for row in rows],
        base_scale_m,
    )
    for row in rows:
        row["decay_exponent"] = decay["exponent"]
        row["decay_r2"] = decay["r2"]
    return rows
