"""Nuth and Kaab co-registration of two bare-earth elevation grids.

Reference: Nuth and Kaab (2011), doi:10.5194/tc-5-271-2011. The elevation
difference between two grids of the same terrain, normalised by slope, varies
as a cosine of aspect whose amplitude and phase give the horizontal offset.

On a 30 degree slope, one metre of horizontal misalignment produces about
0.58 m of apparent vertical change, which is the same order as nine years of
oak height growth. Co-registration is therefore not optional here.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.lidar.raster import shift_bilinear, slope_aspect


def _usable_mask(
    difference: NDArray[np.float64],
    slope: NDArray[np.float64],
    min_slope_deg: float,
    max_slope_deg: float,
) -> NDArray[np.bool_]:
    """Flat ground carries no horizontal information; very steep ground is noisy."""
    if not 0.0 <= min_slope_deg < max_slope_deg:
        raise ValueError("Require 0 <= min_slope_deg < max_slope_deg")

    slope_degrees = np.degrees(slope)
    return (
        np.isfinite(difference)
        & np.isfinite(slope)
        & (slope_degrees >= min_slope_deg)
        & (slope_degrees <= max_slope_deg)
    )


def _system(
    reference: ArrayLike,
    moving: ArrayLike,
    resolution: float,
    min_slope_deg: float,
    max_slope_deg: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Design matrix, observations and slope tangents of one grid pair."""
    reference_grid = np.asarray(reference, dtype=np.float64)
    moving_grid = np.asarray(moving, dtype=np.float64)
    if reference_grid.shape != moving_grid.shape:
        raise ValueError("Reference and moving grids must have the same shape")

    difference = moving_grid - reference_grid
    slope, aspect = slope_aspect(reference_grid, resolution)
    usable = _usable_mask(difference, slope, min_slope_deg, max_slope_deg)

    tangent = np.tan(slope[usable])
    normalised = difference[usable] / tangent
    angle = aspect[usable]
    design = np.column_stack([np.sin(angle), np.cos(angle), np.ones_like(angle)])
    return design, normalised, tangent


def _solve(
    design: NDArray[np.float64],
    normalised: NDArray[np.float64],
    tangent: NDArray[np.float64],
) -> dict[str, float]:
    """Least squares solution of the assembled system."""
    if design.shape[0] < 3:
        raise ValueError("Too few usable cells to estimate a shift")

    solution, *_ = np.linalg.lstsq(design, normalised, rcond=None)
    return {
        "dx_m": float(-solution[0]),
        "dy_m": float(-solution[1]),
        "dz_m": float(solution[2] * np.mean(tangent)),
        "cells": float(design.shape[0]),
    }


def estimate_shift(
    reference: ArrayLike,
    moving: ArrayLike,
    resolution: float,
    min_slope_deg: float = 5.0,
    max_slope_deg: float = 45.0,
) -> dict[str, float]:
    """Estimate the offset of the moving grid relative to the reference.

    The returned offset satisfies moving(x, y) = reference(x + dx, y + dy) + dz
    to first order.
    """
    return _solve(
        *_system(reference, moving, resolution, min_slope_deg, max_slope_deg)
    )


def estimate_pooled_shift(
    pairs: list[tuple[ArrayLike, ArrayLike]],
    resolution: float,
    min_slope_deg: float = 5.0,
    max_slope_deg: float = 45.0,
) -> dict[str, float]:
    """One offset solved from every tile at once.

    A tile a few hundred metres across spans too narrow a range of aspect to
    determine a horizontal offset on its own, and the offset is a property of
    the two acquisitions rather than of the tile. The rows every tile
    contributes are therefore stacked and solved together.
    """
    if not pairs:
        raise ValueError("At least one grid pair is required")

    designs, observations, tangents = [], [], []
    for reference, moving in pairs:
        design, normalised, tangent = _system(
            reference, moving, resolution, min_slope_deg, max_slope_deg
        )
        if design.shape[0]:
            designs.append(design)
            observations.append(normalised)
            tangents.append(tangent)

    if not designs:
        raise ValueError("Too few usable cells to estimate a shift")
    return _solve(
        np.vstack(designs), np.concatenate(observations), np.concatenate(tangents)
    )


def align(
    reference: ArrayLike,
    moving: ArrayLike,
    resolution: float,
    min_slope_deg: float = 5.0,
    max_slope_deg: float = 45.0,
    max_iterations: int = 30,
    tolerance_m: float = 0.01,
) -> dict[str, float]:
    """Iterate the shift estimate until the horizontal correction converges."""
    if max_iterations < 1:
        raise ValueError("Iteration limit must be positive")

    reference_grid = np.asarray(reference, dtype=np.float64)
    current = np.asarray(moving, dtype=np.float64).copy()
    total = {"dx_m": 0.0, "dy_m": 0.0, "dz_m": 0.0}
    iterations = 0
    converged = False

    while iterations < max_iterations:
        iterations += 1
        step = estimate_shift(
            reference_grid, current, resolution, min_slope_deg, max_slope_deg
        )
        for key in total:
            total[key] += step[key]
        current = apply_shift(current, step, resolution)
        if np.hypot(step["dx_m"], step["dy_m"]) < tolerance_m:
            converged = True
            break

    return {
        **total,
        "magnitude_m": float(np.hypot(total["dx_m"], total["dy_m"])),
        "iterations": float(iterations),
        "converged": float(converged),
        "rmse_before_m": residual_rmse(reference_grid, moving, resolution),
        "rmse_after_m": residual_rmse(reference_grid, current, resolution),
    }


def apply_shift(
    moving: ArrayLike, shift: dict[str, float], resolution: float
) -> NDArray[np.float64]:
    """Correct a moving elevation grid by the negative of an estimated offset."""
    return apply_horizontal_shift(moving, shift, resolution) - shift["dz_m"]


def apply_horizontal_shift(
    moving: ArrayLike, shift: dict[str, float], resolution: float
) -> NDArray[np.float64]:
    """Correct a moving grid horizontally only.

    A canopy height grid is a surface minus a terrain measured inside one
    epoch, so the vertical datum has already cancelled. Applying the terrain
    vertical offset to it would put the datum back in.
    """
    return shift_bilinear(moving, -shift["dx_m"], -shift["dy_m"], resolution)


def residual_rmse(reference: ArrayLike, moving: ArrayLike, resolution: float) -> float:
    """Root mean squared elevation difference over cells valid in both grids."""
    reference_grid = np.asarray(reference, dtype=np.float64)
    moving_grid = np.asarray(moving, dtype=np.float64)
    difference = moving_grid - reference_grid
    slope, _ = slope_aspect(reference_grid, resolution)
    usable = np.isfinite(difference) & np.isfinite(slope)
    if not usable.any():
        return float("nan")
    return float(np.sqrt(np.mean(difference[usable] ** 2)))


def accept(shift: dict[str, float], max_accepted_shift_m: float) -> bool:
    """A tile passes when the solver converged within the accepted magnitude."""
    return bool(shift["converged"]) and shift["magnitude_m"] <= max_accepted_shift_m


def align_pooled(
    pairs: list[tuple[ArrayLike, ArrayLike]],
    resolution: float,
    min_slope_deg: float = 5.0,
    max_slope_deg: float = 45.0,
    max_iterations: int = 30,
    tolerance_m: float = 0.01,
) -> dict[str, float]:
    """Iterate the pooled estimate until the horizontal correction converges."""
    if max_iterations < 1:
        raise ValueError("Iteration limit must be positive")
    if not pairs:
        raise ValueError("At least one grid pair is required")

    references = [np.asarray(reference, dtype=np.float64) for reference, _ in pairs]
    originals = [np.asarray(moving, dtype=np.float64) for _, moving in pairs]
    current = [grid.copy() for grid in originals]
    total = {"dx_m": 0.0, "dy_m": 0.0, "dz_m": 0.0}
    iterations = 0
    converged = False
    cells = 0.0

    while iterations < max_iterations:
        iterations += 1
        step = estimate_pooled_shift(
            list(zip(references, current, strict=True)),
            resolution,
            min_slope_deg,
            max_slope_deg,
        )
        cells = step["cells"]
        for key in total:
            total[key] += step[key]
        current = [apply_shift(grid, step, resolution) for grid in current]
        if np.hypot(step["dx_m"], step["dy_m"]) < tolerance_m:
            converged = True
            break

    before = [
        residual_rmse(reference, grid, resolution)
        for reference, grid in zip(references, originals, strict=True)
    ]
    after = [
        residual_rmse(reference, grid, resolution)
        for reference, grid in zip(references, current, strict=True)
    ]
    return {
        **total,
        "magnitude_m": float(np.hypot(total["dx_m"], total["dy_m"])),
        "iterations": float(iterations),
        "converged": float(converged),
        "tiles": float(len(pairs)),
        "cells": float(cells),
        "rmse_before_m": float(np.nanmean(before)),
        "rmse_after_m": float(np.nanmean(after)),
    }
