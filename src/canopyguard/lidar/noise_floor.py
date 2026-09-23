"""Build matched canopy surfaces over a tile sample and measure the floor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.evaluation.detectability import noise_floor_table
from canopyguard.lidar.coreg import align_pooled, apply_shift, residual_rmse
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
    shift: dict[str, float],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Apply the gate conditions to a measured noise floor."""
    if not rows:
        raise ValueError("Gate needs at least one measured scale")

    by_scale = {row["scale_m"]: row for row in rows}
    sigmas = [row["sigma_m"] for row in rows]
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
        "coregistration_converged": bool(shift["converged"]),
        "shift_below_limit": bool(shift["magnitude_m"] < thresholds["max_shift_m"]),
        "sigma_at_reference_below_limit": bool(
            by_scale.get(reference, {}).get("sigma_m", float("inf"))
            < thresholds["max_sigma_at_reference_m"]
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "shift_m": shift["magnitude_m"],
        "tiles": shift["tiles"],
    }


def _load_pairs(
    plan: dict[str, Any], out_dir: str | Path, epochs: tuple[str, str]
) -> list[dict[str, Any]]:
    """Read both surfaces of both epochs for every tile that has all four."""
    from canopyguard.lidar.gridio import read_grid

    start, end = epochs
    loaded = []
    for index in complete_tiles(plan, out_dir, epochs):
        first = surface_paths(out_dir, start, index)
        second = surface_paths(out_dir, end, index)
        terrain_a, profile = read_grid(first["dtm"])
        surface_a, _ = read_grid(first["dsm"])
        terrain_b, _ = read_grid(second["dtm"])
        surface_b, _ = read_grid(second["dsm"])
        shapes = {grid.shape for grid in (terrain_a, surface_a, terrain_b, surface_b)}
        if len(shapes) != 1:
            continue
        loaded.append(
            {
                "index": index,
                "profile": profile,
                "paths": (first, second),
                "terrain": (terrain_a, terrain_b),
                "surface": (surface_a, surface_b),
            }
        )
    return loaded


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

    loaded = _load_pairs(plan, out_dir, epochs)
    if not loaded:
        raise ValueError("No tile has all four surfaces on a common grid")

    shift = align_pooled(
        [tile["terrain"] for tile in loaded],
        resolution,
        settings["min_slope_deg"],
        settings["max_slope_deg"],
        settings["max_iterations"],
        settings["convergence_tolerance_m"],
    )

    residuals: list[dict[str, float]] = []
    deltas: list[dict[float, NDArray[np.float64]]] = []
    for tile in loaded:
        terrain_a, terrain_b = tile["terrain"]
        surface_a, surface_b = tile["surface"]
        first, second = tile["paths"]

        height_a = canopy_height(surface_a, terrain_a, config)
        height_b = apply_shift(
            canopy_height(surface_b, terrain_b, config), shift, resolution
        )
        write_grid(first["chm"], height_a, tile["profile"])
        write_grid(second["chm"], height_b, tile["profile"])
        residuals.append(
            {
                "tile": float(tile["index"]),
                "rmse_before_m": residual_rmse(terrain_a, terrain_b, resolution),
                "rmse_after_m": residual_rmse(
                    terrain_a, apply_shift(terrain_b, shift, resolution), resolution
                ),
            }
        )
        deltas.append(
            difference_ladder(
                height_a,
                height_b,
                resolution,
                aggregation["scales_m"],
                aggregation["min_valid_fraction"],
            )
        )

    rows = noise_floor_table(pool_ladder(deltas), base_scale_m=resolution)
    return {
        "rows": rows,
        "shift": shift,
        "residuals": residuals,
        "gate": evaluate_gate(rows, shift, config["noise_floor"]["gate"]),
    }
