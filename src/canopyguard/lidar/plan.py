"""Work plan for building matched canopy height rasters over a sample."""

from __future__ import annotations

import math
from typing import Any

from canopyguard.lidar.ept import reader_stage
from canopyguard.lidar.grid import tile_grid_geometry
from canopyguard.lidar.harmonize import sample_radius_for, screen_epochs
from canopyguard.lidar.sources import co_covered_tiles, footprint, union_box
from canopyguard.lidar.tiles import sample_area_km2, spatial_stratum, stratified_sample

Box = tuple[float, float, float, float]


def search_box(lidar_config: dict[str, Any]) -> Box:
    """Region the noise-floor overlap is looked for inside."""
    box = lidar_config["noise_floor"].get("search_box")
    if not box:
        raise ValueError("noise_floor.search_box is not set")
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


def noise_floor_footprints(lidar_config: dict[str, Any]) -> dict[str, list[Box]]:
    """Delivered-file boxes of each epoch in the noise-floor pair.

    This reads the source manifests over the network. Everything downstream
    takes the footprints as data, so the plan is reproducible from a saved
    pair of manifests.
    """
    return {
        epoch: footprint(project)
        for epoch, project in sorted(noise_floor_projects(lidar_config).items())
    }


def dispersion_grid_side(tile_count: int) -> int:
    """Side of the coarse grid the sample is spread over.

    The grid must not create more strata than there are tiles to draw, so the
    side is the largest value whose square fits inside the sample.
    """
    if tile_count < 1:
        raise ValueError("Tile count must be positive")
    return max(1, int(math.isqrt(tile_count)))


def calibration_tiles(
    lidar_config: dict[str, Any], footprints: dict[str, list[Box]]
) -> list[Box]:
    """Every tile inside the search box that both epochs supply in full.

    Two work units that merely abut share a seam of half-overlapping delivery
    tiles. A tile wider than that seam is covered by one epoch only, so tile
    size is checked against the coverage rather than assumed.
    """
    wanted = set(lidar_config["noise_floor"]["epoch_pair"])
    missing = wanted - set(footprints)
    if missing:
        raise ValueError("No footprint for epochs: " + ", ".join(sorted(missing)))

    tiers = lidar_config["tiers"]
    return co_covered_tiles(
        [footprints[epoch] for epoch in sorted(wanted)],
        search_box(lidar_config),
        float(tiers["sample_tile_size_m"]),
        int(tiers["coverage_cells_per_tile"]),
    )


def calibration_plan(
    lidar_config: dict[str, Any],
    tile_count: int,
    footprints: dict[str, list[Box]],
    seed: int | None = None,
) -> dict[str, Any]:
    """Tiles, reader stages, rasters grids and sampling radius for the build."""
    results = screen_epochs(lidar_config)
    radius = sample_radius_for(lidar_config, results)
    projects = noise_floor_projects(lidar_config)

    candidates = calibration_tiles(lidar_config, footprints)
    if not candidates:
        raise ValueError("No tile is covered in full by every noise-floor epoch")

    extent = union_box(candidates)
    side = dispersion_grid_side(tile_count)
    chosen = stratified_sample(
        candidates,
        lambda tile: spatial_stratum(extent, tile, side, side),
        min(tile_count, len(candidates)),
        seed if seed is not None else int(lidar_config["tiers"]["seed"]),
    )

    crs = lidar_config["harmonization"]["target_crs"]
    resolution = float(lidar_config["chm"]["resolution_m"])

    return {
        "search_box": list(search_box(lidar_config)),
        "coverage_box": list(extent),
        "tile_size_m": float(lidar_config["tiers"]["sample_tile_size_m"]),
        "candidate_tiles": len(candidates),
        "candidate_area_km2": sample_area_km2(candidates),
        "dispersion_grid_side": side,
        "tile_count": len(chosen),
        "sample_area_km2": sample_area_km2(chosen),
        "sample_radius_m": radius,
        "projects": projects,
        "tiles": [
            {
                "index": index,
                "box": list(tile),
                "grid": tile_grid_geometry(tile, crs, resolution),
                "readers": {
                    epoch: reader_stage(project, tile)
                    for epoch, project in sorted(projects.items())
                },
            }
            for index, tile in enumerate(chosen)
        ],
    }
