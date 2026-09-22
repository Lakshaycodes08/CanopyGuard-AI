"""Aggregation ladder and epoch differencing for canopy height grids."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.lidar.raster import block_reduce


def scale_factor(base_resolution_m: float, scale_m: float) -> int:
    """Integer block factor taking the base grid to a target scale."""
    if base_resolution_m <= 0 or scale_m <= 0:
        raise ValueError("Resolutions must be positive")
    ratio = scale_m / base_resolution_m
    factor = int(round(ratio))
    if abs(ratio - factor) > 1e-9:
        raise ValueError(f"Scale {scale_m} is not a multiple of {base_resolution_m}")
    return factor


def aggregate_ladder(
    grid: ArrayLike,
    base_resolution_m: float,
    scales_m: list[float],
    statistic: str = "mean",
    min_valid_fraction: float = 0.5,
) -> dict[float, NDArray[np.float64]]:
    """Aggregate one grid to every scale in the ladder."""
    return {
        float(scale): block_reduce(
            grid,
            scale_factor(base_resolution_m, scale),
            statistic,
            min_valid_fraction,
        )
        for scale in scales_m
    }


def difference(start: ArrayLike, end: ArrayLike) -> NDArray[np.float64]:
    """Canopy height change from the earlier epoch to the later one."""
    first = np.asarray(start, dtype=np.float64)
    second = np.asarray(end, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("Both epochs must share a grid")
    return second - first


def difference_ladder(
    start: ArrayLike,
    end: ArrayLike,
    base_resolution_m: float,
    scales_m: list[float],
    min_valid_fraction: float = 0.5,
) -> dict[float, NDArray[np.float64]]:
    """Aggregate both epochs, then difference at each scale.

    Aggregating before differencing keeps the valid-fraction rule acting on
    each epoch separately, so a cell thin in one epoch cannot pass by
    borrowing coverage from the other.
    """
    first = aggregate_ladder(
        start, base_resolution_m, scales_m, "mean", min_valid_fraction
    )
    second = aggregate_ladder(
        end, base_resolution_m, scales_m, "mean", min_valid_fraction
    )
    return {scale: difference(first[scale], second[scale]) for scale in first}


def annualise(delta: ArrayLike, baseline_years: float) -> NDArray[np.float64]:
    """Mean annual rate implied by a change over a temporal baseline."""
    if baseline_years <= 0:
        raise ValueError("Temporal baseline must be positive")
    return np.asarray(delta, dtype=np.float64) / baseline_years


def apply_mask(delta: ArrayLike, keep: ArrayLike) -> NDArray[np.float64]:
    """Blank cells outside a stratum, keeping the grid shape."""
    values = np.asarray(delta, dtype=np.float64)
    selected = np.asarray(keep, dtype=bool)
    if values.shape != selected.shape:
        raise ValueError("Mask must match the grid shape")
    return np.where(selected, values, np.nan)


def summarise(delta: ArrayLike) -> dict[str, float]:
    """Location and spread of a change grid over its valid cells."""
    values = np.asarray(delta, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Change grid has no valid cells")
    return {
        "cells": float(values.size),
        "mean_m": float(np.mean(values)),
        "median_m": float(np.median(values)),
        "sd_m": float(np.std(values, ddof=1)) if values.size > 1 else float("nan"),
        "p5_m": float(np.percentile(values, 5)),
        "p95_m": float(np.percentile(values, 95)),
    }
