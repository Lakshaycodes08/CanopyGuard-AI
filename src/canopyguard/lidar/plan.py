"""Work plan for building matched canopy height rasters over a sample."""

from __future__ import annotations

import math
from typing import Any

from canopyguard.lidar.chm import vertical_scale_stage
from canopyguard.lidar.ept import reader_stage
from canopyguard.lidar.footprint import intersect
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


def epoch_datasets(epoch: dict[str, Any]) -> list[str]:
    """Entwine resources an epoch is published as.

    An epoch names one resource under `dataset` or several under `datasets`.
    """
    names = epoch.get("datasets", epoch.get("dataset"))
    if isinstance(names, str):
        names = [names]
    datasets = [str(name) for name in names or []]
    if not datasets:
        raise ValueError(f"Epoch {epoch.get('name')} names no dataset")
    return datasets


def epoch_projects(
    lidar_config: dict[str, Any], epochs: list[str] | tuple[str, ...]
) -> dict[str, list[str]]:
    """Resource names of each requested epoch."""
    wanted = set(epochs)
    projects = {
        epoch["name"]: epoch_datasets(epoch)
        for epoch in lidar_config["epochs"]
        if epoch["name"] in wanted
    }
    missing = wanted - set(projects)
    if missing:
        raise ValueError("No dataset for epochs: " + ", ".join(sorted(missing)))
    return projects


def noise_floor_projects(lidar_config: dict[str, Any]) -> dict[str, str]:
    """Dataset name of each epoch in the noise-floor pair."""
    projects = epoch_projects(lidar_config, lidar_config["noise_floor"]["epoch_pair"])
    several = sorted(name for name, names in projects.items() if len(names) != 1)
    if several:
        raise ValueError(
            "Noise-floor epochs must name one dataset: " + ", ".join(several)
        )
    return {name: names[0] for name, names in projects.items()}


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


def draw_tiles(
    lidar_config: dict[str, Any],
    candidates: list[Box],
    tile_count: int,
    seed: int | None = None,
) -> tuple[Box, int, list[Box]]:
    """Spread a sample of tiles across the extent of the candidates.

    Returns the extent, the side of the dispersion grid and the drawn tiles.
    """
    extent = union_box(candidates)
    side = dispersion_grid_side(tile_count)
    chosen = stratified_sample(
        candidates,
        lambda tile: spatial_stratum(extent, tile, side, side),
        min(tile_count, len(candidates)),
        seed if seed is not None else int(lidar_config["tiers"]["seed"]),
    )
    return extent, side, chosen


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

    extent, side, chosen = draw_tiles(lidar_config, candidates, tile_count, seed)

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


def pair_projects(
    lidar_config: dict[str, Any], pair: list[str] | tuple[str, str]
) -> dict[str, list[str]]:
    """Resource names of each epoch of a change pair."""
    if len(pair) != 2 or pair[0] == pair[1]:
        raise ValueError("A change pair names two different epochs")
    return epoch_projects(lidar_config, list(pair))


def resource_footprints(projects: dict[str, list[str]]) -> dict[str, list[Box]]:
    """Delivered-file boxes of every resource, keyed by resource name.

    This reads the source manifests over the network.
    """
    names = sorted({name for names in projects.values() for name in names})
    return {name: footprint(name) for name in names}


def epoch_resource_footprints(
    projects: dict[str, list[str]], footprints_by_resource: dict[str, list[Box]]
) -> dict[str, dict[str, list[Box]]]:
    """Delivered-file boxes of each epoch, kept apart by resource."""
    missing = sorted(
        name
        for names in projects.values()
        for name in names
        if name not in footprints_by_resource
    )
    if missing:
        raise ValueError("No footprint for resources: " + ", ".join(missing))
    return {
        epoch: {name: list(footprints_by_resource[name]) for name in names}
        for epoch, names in projects.items()
    }


def epoch_footprint(by_resource: dict[str, list[Box]]) -> list[Box]:
    """Footprint of an epoch as the boxes of all its resources together."""
    return [tuple(box) for name in sorted(by_resource) for box in by_resource[name]]


def tile_resources(tile: Box, by_resource: dict[str, list[Box]]) -> list[str]:
    """Resources holding a delivered file that meets the tile."""
    return [
        name
        for name in sorted(by_resource)
        if any(intersect(tuple(box), tile) is not None for box in by_resource[name])
    ]


def change_tiles(
    lidar_config: dict[str, Any],
    study_box: Box,
    footprints: dict[str, list[Box]],
) -> list[Box]:
    """Every change tile inside the study box that both epochs supply in full."""
    return co_covered_tiles(
        [footprints[epoch] for epoch in sorted(footprints)],
        tuple(float(value) for value in study_box),
        float(lidar_config["change"]["tile_size_m"]),
        int(lidar_config["tiers"]["coverage_cells_per_tile"]),
    )


def epoch_unit_stages(lidar_config: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Unit conversion for an epoch whose elevations are not stored in metres."""
    for epoch in lidar_config["epochs"]:
        if str(epoch["name"]) == str(name):
            factor = float(epoch.get("z_to_metres", 1.0))
            return [] if factor == 1.0 else [vertical_scale_stage(factor)]
    raise ValueError(f"No epoch named: {name}")


def change_plan(
    lidar_config: dict[str, Any],
    study_box: Box,
    pair: list[str] | tuple[str, str],
    footprints_by_resource: dict[str, list[Box]],
    tile_count: int,
    seed: int | None = None,
) -> dict[str, Any]:
    """Tiles, reader stages, raster grids and sampling radius for a change pair.

    An epoch published as several resources gets one reader per resource that
    meets the tile, and the readers are merged when the pipeline is built.
    """
    results = screen_epochs(lidar_config)
    radius = sample_radius_for(lidar_config, results)
    projects = pair_projects(lidar_config, pair)
    by_epoch = epoch_resource_footprints(projects, footprints_by_resource)

    candidates = change_tiles(
        lidar_config,
        study_box,
        {epoch: epoch_footprint(boxes) for epoch, boxes in by_epoch.items()},
    )
    if not candidates:
        raise ValueError("No tile is covered in full by both epochs of the pair")

    extent, side, chosen = draw_tiles(lidar_config, candidates, tile_count, seed)
    crs = lidar_config["harmonization"]["target_crs"]
    resolution = float(lidar_config["chm"]["resolution_m"])

    return {
        "pair": [str(epoch) for epoch in pair],
        "study_box": [float(value) for value in study_box],
        "coverage_box": list(extent),
        "tile_size_m": float(lidar_config["change"]["tile_size_m"]),
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
                    epoch: [
                        reader_stage(name, tile)
                        for name in tile_resources(tile, by_epoch[epoch])
                    ]
                    + epoch_unit_stages(lidar_config, epoch)
                    for epoch in sorted(by_epoch)
                },
            }
            for index, tile in enumerate(chosen)
        ],
    }
