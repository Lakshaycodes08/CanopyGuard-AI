"""Build matched canopy surfaces over a tile sample and measure the floor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.evaluation.detectability import noise_floor_table
from canopyguard.lidar.coreg import accept, align, apply_shift
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
    shifts: list[dict[str, float]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Apply the gate conditions to a measured noise floor."""
    if not rows:
        raise ValueError("Gate needs at least one measured scale")

    by_scale = {row["scale_m"]: row for row in rows}
    sigmas = [row["sigma_m"] for row in rows]
    accepted = [shift for shift in shifts if shift.get("accepted")]
    median_shift = (
        float(np.median([shift["magnitude_m"] for shift in accepted]))
        if accepted
        else float("nan")
    )
    finest = by_scale[min(by_scale)]
    low, high = thresholds["mean_one_year_change_m"]
    reference = thresholds["sigma_reference_scale_m"]

    checks = {
        "mean_one_year_change_in_range": bool(low <= finest["mean_m"] <= high),
        "sigma_falls_with_scale": bool(
            all(
                later <= earlier
                for earlier, later in zip(sigmas, sigmas[1:], strict=False)
            )
        ),
        "median_tile_shift_below_limit": bool(
            median_shift < thresholds["max_median_shift_m"]
        ),
        "sigma_at_reference_below_limit": bool(
            by_scale.get(reference, {}).get("sigma_m", float("inf"))
            < thresholds["max_sigma_at_reference_m"]
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "median_shift_m": median_shift,
        "accepted_tiles": len(accepted),
        "evaluated_tiles": len(shifts),
    }


def measure(
    plan: dict[str, Any], out_dir: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Co-register each tile pair, difference it, and pool the result."""
    from canopyguard.lidar.gridio import read_grid, write_grid

    settings = config["coregistration"]
    resolution = config["chm"]["resolution_m"]
    aggregation = config["aggregation"]
    start, end = tuple(config["noise_floor"]["epoch_pair"])

    shifts: list[dict[str, float]] = []
    deltas: list[dict[float, NDArray[np.float64]]] = []

    for index in complete_tiles(plan, out_dir, (start, end)):
        first = surface_paths(out_dir, start, index)
        second = surface_paths(out_dir, end, index)
        dtm_a, profile = read_grid(first["dtm"])
        dsm_a, _ = read_grid(first["dsm"])
        dtm_b, _ = read_grid(second["dtm"])
        dsm_b, _ = read_grid(second["dsm"])
        if dtm_a.shape != dtm_b.shape:
            continue

        shift = align(
            dtm_a,
            dtm_b,
            resolution,
            settings["min_slope_deg"],
            settings["max_slope_deg"],
            settings["max_iterations"],
            settings["convergence_tolerance_m"],
        )
        shift["tile"] = float(index)
        shift["accepted"] = float(accept(shift, settings["max_accepted_shift_m"]))
        shifts.append(shift)
        if not shift["accepted"]:
            continue

        chm_a = canopy_height(dsm_a, dtm_a, config)
        chm_b = apply_shift(canopy_height(dsm_b, dtm_b, config), shift, resolution)
        write_grid(first["chm"], chm_a, profile)
        write_grid(second["chm"], chm_b, profile)
        deltas.append(
            difference_ladder(
                chm_a,
                chm_b,
                resolution,
                aggregation["scales_m"],
                aggregation["min_valid_fraction"],
            )
        )

    rows = noise_floor_table(pool_ladder(deltas), base_scale_m=resolution)
    return {
        "rows": rows,
        "shifts": shifts,
        "gate": evaluate_gate(rows, shifts, config["noise_floor"]["gate"]),
    }
