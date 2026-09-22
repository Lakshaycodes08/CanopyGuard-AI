"""Work plan for building matched canopy height rasters over a sample."""

from __future__ import annotations

import math
from typing import Any

from canopyguard.lidar.ept import reader_stage
from canopyguard.lidar.harmonize import sample_radius_for, screen_epochs
from canopyguard.lidar.tiles import (
    sample_area_km2,
    spatial_stratum,
    stratified_sample,
    tile_grid,
)


def calibration_box(lidar_config: dict[str, Any]) -> tuple[float, float, float, float]:
    """Area where the noise-floor epochs overlap."""
    box = lidar_config["noise_floor"].get("verified_intersection")
    if not box:
        raise ValueError("noise_floor.verified_intersection is not set")
    return tuple(float(value) for value in box)


def noise_floor_projects(lidar_config: dict[str, Any]) -> dict[str, str]:
    """Dataset name of each epoch in the noise-floor pair."""
    wanted = set(lidar_config["noise_floor"]["epoch_pair"])
    projects = {
        epoch["name"]: epoch["dataset"]
        for epoch in lidar_config["epochs"]
        if epoch["name"] in wanted
    }
    missing = wanted - set(projects)
    if missing:
        raise ValueError("No dataset for epochs: " + ", ".join(sorted(missing)))
    return projects


def dispersion_grid_side(tile_count: int) -> int:
    """Side of the coarse grid the sample is spread over.

    The grid must not create more strata than there are tiles to draw, so the
    side is the largest value whose square fits inside the sample.
    """
    if tile_count < 1:
        raise ValueError("Tile count must be positive")
    return max(1, int(math.isqrt(tile_count)))


def calibration_plan(
    lidar_config: dict[str, Any], tile_count: int, seed: int | None = None
) -> dict[str, Any]:
    """Tiles, reader stages and sampling radius for the noise-floor build."""
    results = screen_epochs(lidar_config)
    radius = sample_radius_for(lidar_config, results)
    box = calibration_box(lidar_config)
    projects = noise_floor_projects(lidar_config)

    size = float(lidar_config["tiers"]["sample_tile_size_m"])
    candidates = tile_grid(box, size)
    side = dispersion_grid_side(tile_count)
    chosen = stratified_sample(
        candidates,
        lambda tile: spatial_stratum(box, tile, side, side),
        tile_count,
        seed if seed is not None else int(lidar_config["tiers"]["seed"]),
    )

    return {
        "calibration_box": list(box),
        "tile_size_m": size,
        "dispersion_grid_side": side,
        "tile_count": len(chosen),
        "sample_area_km2": sample_area_km2(chosen),
        "sample_radius_m": radius,
        "projects": projects,
        "tiles": [
            {
                "index": index,
                "box": list(tile),
                "readers": {
                    epoch: reader_stage(project, tile)
                    for epoch, project in sorted(projects.items())
                },
            }
            for index, tile in enumerate(chosen)
        ],
    }
