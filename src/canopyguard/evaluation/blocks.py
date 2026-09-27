"""Spatial blocking driven by the residual variogram, and dispersed folds."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


def assign_blocks(
    easting: ArrayLike, northing: ArrayLike, block_size_m: float
) -> NDArray[np.int64]:
    """Label points by the square block of the given edge length."""
    if block_size_m <= 0:
        raise ValueError("Block size must be positive")

    x = np.asarray(easting, dtype=np.float64).ravel()
    y = np.asarray(northing, dtype=np.float64).ravel()
    if x.shape != y.shape:
        raise ValueError("Coordinate arrays must have the same shape")

    columns = np.floor((x - x.min()) / block_size_m).astype(np.int64)
    rows = np.floor((y - y.min()) / block_size_m).astype(np.int64)
    return rows * (columns.max() + 1) + columns


def systematic_folds(
    block_ids: ArrayLike, n_folds: int, seed: int = 42
) -> NDArray[np.int64]:
    """Assign blocks to folds so that each fold is spatially dispersed.

    Blocks are shuffled once and dealt round robin, so a fold never receives a
    contiguous run of neighbouring blocks.
    """
    if n_folds < 2:
        raise ValueError("Fold count must be at least two")

    ids = np.asarray(block_ids).ravel()
    unique = np.unique(ids)
    if unique.size < n_folds:
        raise ValueError("Fold count cannot exceed the number of blocks")

    shuffled = np.random.default_rng(seed).permutation(unique)
    fold_of_block = {
        block: index % n_folds for index, block in enumerate(shuffled.tolist())
    }
    return np.array([fold_of_block[value] for value in ids.tolist()], dtype=np.int64)


def empirical_variogram(
    easting: ArrayLike,
    northing: ArrayLike,
    values: ArrayLike,
    lag_m: float,
    max_distance_m: float,
    max_pairs: int = 2_000_000,
    seed: int = 42,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
    """Return lag centres, semivariance, and pair counts for point residuals."""
    if lag_m <= 0 or max_distance_m <= lag_m:
        raise ValueError("Require 0 < lag_m < max_distance_m")

    x = np.asarray(easting, dtype=np.float64).ravel()
    y = np.asarray(northing, dtype=np.float64).ravel()
    z = np.asarray(values, dtype=np.float64).ravel()
    if not x.shape == y.shape == z.shape:
        raise ValueError("Coordinates and values must have the same shape")

    left, right = _pair_indices(x.size, max_pairs, seed)
    separation = np.hypot(x[left] - x[right], y[left] - y[right])
    squared = 0.5 * (z[left] - z[right]) ** 2

    edges = np.arange(0.0, max_distance_m + lag_m, lag_m)
    bins = np.digitize(separation, edges) - 1
    inside = (bins >= 0) & (bins < edges.size - 1)

    width = edges.size - 1
    counts = np.bincount(bins[inside], minlength=width)
    totals = np.bincount(bins[inside], weights=squared[inside], minlength=width)
    empty = np.full(counts.shape, np.nan)
    gamma = np.divide(totals, counts, out=empty, where=counts > 0)
    return edges[:-1] + lag_m / 2.0, gamma, counts.astype(np.int64)


def _pair_indices(size: int, max_pairs: int, seed: int) -> tuple[NDArray, NDArray]:
    """Return point index pairs, subsampled when the full set is too large."""
    if size < 2:
        raise ValueError("Variogram requires at least two points")

    total = size * (size - 1) // 2
    if total <= max_pairs:
        return np.triu_indices(size, k=1)

    generator = np.random.default_rng(seed)
    left = generator.integers(0, size, size=max_pairs)
    right = generator.integers(0, size, size=max_pairs)
    keep = left != right
    return left[keep], right[keep]


def spherical_model(
    distance: ArrayLike, nugget: float, sill: float, model_range: float
) -> NDArray[np.float64]:
    """Spherical semivariance, flat at nugget plus sill beyond the range."""
    if model_range <= 0:
        raise ValueError("Model range must be positive")

    h = np.asarray(distance, dtype=np.float64)
    ratio = np.clip(h / model_range, 0.0, 1.0)
    shape = 1.5 * ratio - 0.5 * ratio**3
    return nugget + sill * np.where(h >= model_range, 1.0, shape)


def _solve_nugget_sill(
    shape: NDArray[np.float64], gamma: NDArray[np.float64], weight: NDArray[np.float64]
) -> tuple[float, float] | None:
    """Weighted least squares for nugget and sill at a fixed range.

    A negative nugget is clamped to zero and the sill re-solved, rather than
    discarding the candidate range, which would leave only degenerate fits.
    """
    root = np.sqrt(weight)
    design = np.column_stack([np.ones_like(shape), shape])
    solution, *_ = np.linalg.lstsq(design * root[:, None], gamma * root, rcond=None)
    nugget, sill = float(solution[0]), float(solution[1])

    if nugget < 0.0:
        nugget = 0.0
        denominator = float(np.sum(weight * shape**2))
        if denominator == 0.0:
            return None
        sill = float(np.sum(weight * shape * gamma) / denominator)

    return (nugget, sill) if sill > 0.0 else None


def fit_spherical(
    lags: ArrayLike, gamma: ArrayLike, counts: ArrayLike | None = None
) -> dict[str, float]:
    """Fit a spherical variogram by grid search over the range parameter.

    Nugget and sill are solved in closed form for each candidate range, so only
    one parameter is searched.
    """
    h = np.asarray(lags, dtype=np.float64).ravel()
    g = np.asarray(gamma, dtype=np.float64).ravel()
    weight = (
        np.ones_like(h)
        if counts is None
        else np.asarray(counts, dtype=np.float64).ravel()
    )
    valid = np.isfinite(g) & (weight > 0)
    if valid.sum() < 3:
        raise ValueError("Variogram fit requires at least three populated lags")

    h, g, weight = h[valid], g[valid], weight[valid]
    best: dict[str, float] = {}
    best_cost = math.inf

    for candidate in np.linspace(h.min(), h.max(), 200):
        shape = spherical_model(h, 0.0, 1.0, candidate)
        if shape.max() - shape.min() < 1e-12:
            continue
        solved = _solve_nugget_sill(shape, g, weight)
        if solved is None:
            continue
        nugget, sill = solved
        cost = float(np.sum(weight * (g - nugget - sill * shape) ** 2))
        if cost < best_cost:
            best_cost = cost
            best = {"nugget": nugget, "sill": sill, "range_m": float(candidate)}

    if not best:
        raise ValueError("No admissible spherical fit was found")
    return best


def practical_range(fit: dict[str, float], sill_fraction: float = 0.95) -> float:
    """Distance at which the fitted model reaches the given fraction of sill."""
    if not 0.0 < sill_fraction <= 1.0:
        raise ValueError("Sill fraction must lie in (0, 1]")

    grid = np.linspace(0.0, fit["range_m"], 2001)
    modelled = spherical_model(grid, 0.0, fit["sill"], fit["range_m"])
    reached = np.flatnonzero(modelled >= sill_fraction * fit["sill"])
    return float(grid[reached[0]]) if reached.size else float(fit["range_m"])


def select_block_size(
    practical_range_m: float, candidates: list[float], minimum_m: float
) -> float:
    """Smallest candidate block size at or above the residual range."""
    if not candidates:
        raise ValueError("Candidate block sizes must be provided")

    target = max(practical_range_m, minimum_m)
    admissible = sorted(value for value in candidates if value >= target)
    return float(admissible[0]) if admissible else float(max(candidates))
