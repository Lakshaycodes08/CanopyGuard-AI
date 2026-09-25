"""Build matched canopy surfaces over a tile sample and measure the floor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.evaluation.detectability import noise_floor_table
from canopyguard.lidar.coreg import (
    align_pooled,
    apply_horizontal_shift,
    apply_shift,
    residual_rmse,
)
from canopyguard.lidar.difference import difference_ladder


def canopy_height(
    surface: ArrayLike, terrain: ArrayLike, config: dict[str, Any]
) -> NDArray[np.float64]:
    """Canopy height within one epoch, so the vertical datum cancels."""
    chm = config["chm"]
    top = np.asarray(surface, dtype=np.float64)
    ground = np.asarray(terrain, dtype=np.float64)
    if top.shape != ground.shape:
        raise ValueError("Surface and terrain must share a grid")

    height = top - ground
    outside = (height < chm["clamp_min_m"]) | (height > chm["clamp_max_m"])
    return np.where(outside, np.nan, height)


def height_summary(height: ArrayLike) -> dict[str, float]:
    """Canopy height distribution of one tile.

    A measurement made where nothing is standing is a measurement of bare
    ground, whatever the pipeline is called, so the height the sample carries
    is reported alongside the spread of its change.
    """
    values = np.asarray(height, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"cells": 0.0}
    return {
        "cells": float(values.size),
        "median_m": float(np.median(values)),
        "p95_m": float(np.percentile(values, 95)),
        "above_2m": float(np.mean(values > 2.0)),
        "above_5m": float(np.mean(values > 5.0)),
        "above_10m": float(np.mean(values > 10.0)),
    }


def tile_stem(epoch: str, index: int) -> str:
    """Stable name for one epoch of one tile."""
    return f"{epoch}_t{int(index):04d}"


def surface_paths(out_dir: str | Path, epoch: str, index: int) -> dict[str, Path]:
    """Output paths for the surfaces of one epoch of one tile."""
    stem = tile_stem(epoch, index)
    root = Path(out_dir)
    return {
        "dtm": root / f"dtm_{stem}.tif",
        "dsm": root / f"dsm_{stem}.tif",
        "chm": root / f"chm_{stem}.tif",
    }


def complete_tiles(
    plan: dict[str, Any], out_dir: str | Path, epochs: tuple[str, str]
) -> list[int]:
    """Tile indices whose surfaces exist for both epochs."""
    ready = []
    for tile in plan["tiles"]:
        paths = [
            surface_paths(out_dir, epoch, tile["index"])[kind]
            for epoch in epochs
            for kind in ("dtm", "dsm")
        ]
        if all(path.exists() for path in paths):
            ready.append(tile["index"])
    return ready


def admit_tile(
    first: ArrayLike, second: ArrayLike, rules: dict[str, Any]
) -> dict[str, Any]:
    """Decide whether a tile's two surfaces can be differenced.

    The raster writer produces a file even when no point reaches it, so a tile
    outside one acquisition looks built. A tile inside both can still carry a
    tenth of the returns in one epoch, which biases the surface maximum
    downward in that epoch alone, so the two coverages are compared as well as
    counted.
    """
    top = np.asarray(first, dtype=np.float64)
    bottom = np.asarray(second, dtype=np.float64)
    if top.shape != bottom.shape:
        return {"admitted": False, "reason": "grids differ"}

    counts = (int(np.isfinite(top).sum()), int(np.isfinite(bottom).sum()))
    fraction = min(counts) / float(top.size)
    agreement = min(counts) / max(counts) if max(counts) else 0.0
    result = {
        "valid_cells": [float(value) for value in counts],
        "valid_fraction": float(fraction),
        "coverage_agreement": float(agreement),
        "admitted": True,
        "reason": "",
    }
    if fraction < rules["min_valid_fraction"]:
        result.update(admitted=False, reason="coverage below the minimum")
    elif agreement < rules["min_coverage_agreement"]:
        result.update(admitted=False, reason="epoch coverages disagree")
    return result


def stable_heights(
    first: ArrayLike, second: ArrayLike, limit_m: float
) -> tuple[NDArray[np.float64], NDArray[np.float64], tuple[int, int]]:
    """Blank cells whose height changes by more than the limit in both epochs.

    Returns the two masked grids and the counts of stable and of valid cells.
    """
    if limit_m <= 0:
        raise ValueError("Stable change limit must be positive")
    top = np.asarray(first, dtype=np.float64)
    bottom = np.asarray(second, dtype=np.float64)
    if top.shape != bottom.shape:
        raise ValueError("Both epochs must share a grid")
    change = bottom - top
    valid = np.isfinite(change)
    stable = valid & (np.abs(np.where(valid, change, 0.0)) <= limit_m)
    return (
        np.where(stable, top, np.nan),
        np.where(stable, bottom, np.nan),
        (int(stable.sum()), int(valid.sum())),
    )


def pool_ladder(
    deltas: list[dict[float, NDArray[np.float64]]],
) -> dict[float, NDArray[np.float64]]:
    """Concatenate per-tile change grids into one sample per scale."""
    if not deltas:
        raise ValueError("No tile produced a change grid")

    pooled: dict[float, list[NDArray[np.float64]]] = {}
    for entry in deltas:
        for scale, grid in entry.items():
            pooled.setdefault(float(scale), []).append(np.asarray(grid).ravel())
    return {scale: np.concatenate(parts) for scale, parts in pooled.items()}


def evaluate_gate(
    rows: list[dict[str, float]],
    shift: dict[str, float],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Apply the gate conditions to the scales the sample can support.

    Spread may rise between adjacent scales by no more than twice the combined
    relative standard error of the two estimates. A reference scale the sample
    cannot support is taken from the decay fit over at least three admitted
    scales and reported as extrapolated.
    """
    admitted = [row for row in rows if row.get("admitted", True)]
    if not admitted:
        raise ValueError("Gate needs at least one measured scale")

    by_scale = {row["scale_m"]: row for row in admitted}
    sigmas = [row["sigma_m"] for row in admitted]
    finest = by_scale[min(by_scale)]
    low = -float(finest.get("lod95_m", 0.0))
    high = thresholds["max_mean_one_year_change_m"]
    reference = thresholds["sigma_reference_scale_m"]
    errors = [row.get("sigma_relative_error", 0.0) for row in admitted]
    reference_sigma, reference_source = reference_spread(admitted, reference)

    checks = {
        "mean_one_year_change_in_range": bool(low <= finest["mean_m"] <= high),
        "sigma_falls_with_scale": bool(
            all(
                sigmas[i + 1]
                <= sigmas[i] * (1.0 + 2.0 * np.hypot(errors[i], errors[i + 1]))
                for i in range(len(sigmas) - 1)
            )
        ),
        "coregistration_converged": bool(shift["converged"]),
        "shift_below_limit": bool(shift["magnitude_m"] < thresholds["max_shift_m"]),
        "sigma_at_reference_below_limit": bool(
            reference_sigma < thresholds["max_sigma_at_reference_m"]
        ),
        "reference_sigma_available": bool(np.isfinite(reference_sigma)),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "shift_m": shift["magnitude_m"],
        "tiles": shift["tiles"],
        "admitted_scales": [row["scale_m"] for row in admitted],
        "reference_sigma_m": reference_sigma,
        "reference_source": reference_source,
    }


def reference_spread(
    admitted: list[dict[str, float]], reference_m: float
) -> tuple[float, str]:
    """Spread at the reference scale, measured where admitted, else extrapolated."""
    for row in admitted:
        if row["scale_m"] == reference_m:
            return float(row["sigma_m"]), "measured"
    if len(admitted) < 3:
        return float("inf"), "unavailable"
    row = admitted[0]
    coefficient = float(row.get("decay_coefficient", float("nan")))
    exponent = float(row.get("decay_exponent", float("nan")))
    base = float(row.get("decay_base_scale_m", float("nan")))
    if not all(np.isfinite([coefficient, exponent, base])) or base <= 0:
        return float("inf"), "unavailable"
    cells = (float(reference_m) / base) ** 2
    return float(coefficient * cells**-exponent), "extrapolated"


def load_pairs(
    plan: dict[str, Any],
    out_dir: str | Path,
    epochs: tuple[str, str],
    rules: dict[str, Any],
    keep_arrays: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read both surfaces of both epochs and admit the tiles worth using.

    With `keep_arrays` false only paths and profiles are kept, so a large
    sample can be admitted without holding every surface in memory.
    """
    from canopyguard.lidar.gridio import read_grid

    start, end = epochs
    loaded: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []
    for index in complete_tiles(plan, out_dir, epochs):
        first = surface_paths(out_dir, start, index)
        second = surface_paths(out_dir, end, index)
        terrain_a, profile = read_grid(first["dtm"])
        surface_a, _ = read_grid(first["dsm"])
        terrain_b, _ = read_grid(second["dtm"])
        surface_b, _ = read_grid(second["dsm"])

        verdict = {"tile": float(index)}
        shapes = {grid.shape for grid in (terrain_a, surface_a, terrain_b, surface_b)}
        if len(shapes) != 1:
            verdict.update(admitted=False, reason="grids differ")
            verdicts.append(verdict)
            continue

        verdict.update(admit_tile(surface_a, surface_b, rules))
        verdicts.append(verdict)
        if not verdict["admitted"]:
            continue
        entry = {"index": index, "profile": profile, "paths": (first, second)}
        if keep_arrays:
            entry["terrain"] = (terrain_a, terrain_b)
            entry["surface"] = (surface_a, surface_b)
        loaded.append(entry)
    return loaded, verdicts


def measure(
    plan: dict[str, Any], out_dir: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Co-register the sample as one block, difference it, and pool the result.

    The horizontal offset between two acquisitions is a property of the pair,
    not of a tile, and a tile a few hundred metres across does not span enough
    aspect to resolve it alone. One offset is therefore solved from every tile
    together and applied to all of them.
    """
    from canopyguard.lidar.gridio import write_grid

    settings = config["coregistration"]
    resolution = config["chm"]["resolution_m"]
    aggregation = config["aggregation"]
    epochs = tuple(config["noise_floor"]["epoch_pair"])

    loaded, verdicts = load_pairs(
        plan, out_dir, epochs, config["noise_floor"]["tile_admission"]
    )
    if not loaded:
        raise ValueError("No tile passed admission")

    shift = align_pooled(
        [tile["terrain"] for tile in loaded],
        resolution,
        settings["min_slope_deg"],
        settings["max_slope_deg"],
        settings["max_iterations"],
        settings["convergence_tolerance_m"],
    )

    limit = float(config["noise_floor"]["stable_change_limit_m"])
    stable_cells = 0
    valid_cells = 0
    heights: list[dict[str, Any]] = []
    deltas: list[dict[float, NDArray[np.float64]]] = []
    for tile in loaded:
        terrain_a, terrain_b = tile["terrain"]
        surface_a, surface_b = tile["surface"]
        first, second = tile["paths"]

        height_a = canopy_height(surface_a, terrain_a, config)
        height_b = apply_horizontal_shift(
            canopy_height(surface_b, terrain_b, config), shift, resolution
        )
        write_grid(first["chm"], height_a, tile["profile"])
        write_grid(second["chm"], height_b, tile["profile"])
        heights.append(
            {
                "tile": float(tile["index"]),
                epochs[0]: height_summary(height_a),
                epochs[1]: height_summary(height_b),
                "rmse_before_m": residual_rmse(terrain_a, terrain_b, resolution),
                "rmse_after_m": residual_rmse(
                    terrain_a, apply_shift(terrain_b, shift, resolution), resolution
                ),
            }
        )
        stable_a, stable_b, counts = stable_heights(height_a, height_b, limit)
        stable_cells += counts[0]
        valid_cells += counts[1]
        deltas.append(
            difference_ladder(
                stable_a,
                stable_b,
                resolution,
                aggregation["scales_m"],
                aggregation["min_valid_fraction"],
            )
        )

    rows = noise_floor_table(
        pool_ladder(deltas),
        base_scale_m=resolution,
        min_cells=int(aggregation["min_cells_per_scale"]),
    )
    return {
        "rows": rows,
        "shift": shift,
        "tiles": verdicts,
        "heights": heights,
        "stable_fraction": stable_cells / valid_cells if valid_cells else 0.0,
        "gate": evaluate_gate(rows, shift, config["noise_floor"]["gate"]),
    }
