"""How much ground two LiDAR acquisitions share, judged on real returns.

Issue 15. The file-level overlap of two acquisitions is an upper bound. This
module reads the returns over the shared tiles of both epochs and reports the
area where both hold ground and canopy returns, where that area is, and what it
is made of. It is a coverage check, not a canopy change measurement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from canopyguard.config import require_keys
from canopyguard.lidar import (
    burn_state,
    ept_nodes,
    pair_overlap,
    pair_points,
    plan,
    sources,
)
from canopyguard.lidar.pair_tiles import PairRules, analyse_pair
from canopyguard.lidar.tile_stats import (
    PointRules,
    TileStats,
    cell_centres,
    make_tile_grid,
)

Box = tuple[float, float, float, float]
REQUIRED = [
    "earlier",
    "later_epoch",
    "projected_crs",
    "buffers_km",
    "max_depth",
    "threads",
    "request_timeout_seconds",
    "request_retries",
    "canopy_cell_m",
    "min_cell_fraction",
    "min_ground_fraction",
    "noise_classes",
    "water_class",
    "ground_class",
    "excluded_flag_bits",
    "canopy_height_classes_m",
    "usable_canopy_min_km2",
    "sensitivity",
]


def settings(lidar_config: dict[str, Any]) -> dict[str, Any]:
    """The `pair_coverage` section, checked for the keys this module needs."""
    section = lidar_config.get("pair_coverage")
    if not isinstance(section, dict):
        raise ValueError("lidar config has no pair_coverage section")
    require_keys(section, REQUIRED)
    return section


def rules(lidar_config: dict[str, Any]) -> tuple[PointRules, PairRules]:
    """Point and pair rules, reusing the canopy and slope limits already set."""
    own, change, tiers = (
        settings(lidar_config),
        lidar_config["change"],
        lidar_config["tiers"],
    )
    point = PointRules(
        tuple(own["noise_classes"]),
        int(own["water_class"]),
        int(own["ground_class"]),
        int(own["excluded_flag_bits"]),
    )
    pair = PairRules(
        min_cell_fraction=float(own["min_cell_fraction"]),
        min_ground_fraction=float(own["min_ground_fraction"]),
        canopy_min_m=float(change["canopy_min_height_m"]),
        disturbance_limit_m=float(change["disturbance_limit_m"]),
        height_classes_m=tuple(float(v) for v in own["canopy_height_classes_m"]),
        slope_bands_deg=tuple(
            (float(lo), float(hi)) for lo, hi in tiers["slope_bands_deg"]
        ),
        cell_m=float(own["canopy_cell_m"]),
    )
    return point, pair


def epoch_resources(lidar_config: dict[str, Any]) -> dict[str, list[str]]:
    """Resource names of the earlier and later epoch."""
    own = settings(lidar_config)
    later = plan.epoch_projects(lidar_config, [own["later_epoch"]])[own["later_epoch"]]
    return {
        own["earlier"]["name"]: [own["earlier"]["dataset"]],
        own["later_epoch"]: later,
    }


def epoch_boxes(
    resources: list[str], footprint: Callable[[str], list[Box]]
) -> list[Box]:
    """Delivered-file boxes of all resources of one epoch."""
    return [box for name in resources for box in footprint(name)]


def _read_epochs(
    resources: dict[str, list[str]],
    grid,
    point: PointRules,
    own: dict[str, Any],
    fetch: ept_nodes.Fetcher,
    read_points: pair_points.PointReader,
) -> tuple[dict[str, TileStats], dict[str, dict[str, int]]]:
    stats, reads = {}, {}
    for name, projects in resources.items():
        stats[name], reads[name] = pair_points.collect_stats(
            projects, grid, point, own, fetch, read_points
        )
    return stats, reads


def sensitivity(
    grid,
    early: TileStats,
    late: TileStats,
    pair: PairRules,
    burned,
    own: dict[str, Any],
) -> list[dict[str, Any]]:
    """Usable canopy when one threshold at a time is moved."""
    minimum = float(own["usable_canopy_min_km2"])
    rows = []
    for name, values in own["sensitivity"].items():
        for value in values:
            result = analyse_pair(
                grid,
                early,
                late,
                replace(pair, **{name: float(value)}),
                burned,
                minimum,
            )
            rows.append(
                {
                    "parameter": name,
                    "value": float(value),
                    "usable_canopy_km2": result["usable_canopy_km2"],
                    "valid_both_tiles": result["tiles"]["valid_both"],
                    "meets_minimum": result["usable_canopy_meets_minimum"],
                }
            )
    return rows


def run(
    lidar_config: dict[str, Any],
    study_bbox: Box,
    footprint: Callable[[str], list[Box]] = sources.footprint,
    fetch: ept_nodes.Fetcher | None = None,
    read_points: pair_points.PointReader = ept_nodes.read_node_points,
    fetch_json: burn_state.JsonFetcher | None = None,
) -> tuple[dict[str, Any], dict[str, TileStats]]:
    """Measure shared coverage, then read returns over the shared tiles."""
    own = settings(lidar_config)
    point, pair = rules(lidar_config)
    tiers = lidar_config["tiers"]
    resources = epoch_resources(lidar_config)
    first, second = (epoch_boxes(r, footprint) for r in resources.values())
    overlap = pair_overlap.overlap_summary(
        first, second, study_bbox, own["projected_crs"], own["buffers_km"]
    )
    tile_size = float(tiers["sample_tile_size_m"])
    tiles, region = pair_overlap.shared_tiles(
        first, second, tile_size, int(tiers["coverage_cells_per_tile"]), 0.005
    )
    if not tiles:
        return _empty_report(own, resources, overlap, tile_size), {}
    cells = round(tile_size / pair.cell_m)
    grid = make_tile_grid(tiles, cells)
    fetcher = fetch or ept_nodes.make_fetcher(
        own["request_timeout_seconds"], own["request_retries"]
    )
    stats, reads = _read_epochs(resources, grid, point, own, fetcher, read_points)
    perimeters = burn_state.fetch_perimeters(
        own, region, own["request_timeout_seconds"], fetch_json
    )
    burned = burn_state.burned_mask(*cell_centres(grid), perimeters)
    early, late = stats.values()
    result = analyse_pair(
        grid, early, late, pair, burned, float(own["usable_canopy_min_km2"])
    )
    report = _report(
        own, resources, overlap, tile_size, region, reads, perimeters, result
    )
    report["tiles"]["cells_per_tile"] = cells**2
    report["sensitivity"] = sensitivity(grid, early, late, pair, burned, own)
    return report, stats


def _tile_summary(
    tile_size: float, count: int, cells_per_side: int = 0
) -> dict[str, float]:
    return {
        "tile_size_m": tile_size,
        "candidates": count,
        "area_km2": count * (tile_size / 1000.0) ** 2,
        "cells_per_tile": cells_per_side**2,
    }


def _empty_report(own, resources, overlap, tile_size) -> dict[str, Any]:
    return {
        "run_utc": datetime.now(UTC).isoformat(),
        "resources": resources,
        "overlap": overlap,
        "tiles": _tile_summary(tile_size, 0),
        "answer": {
            "shared_tiles": 0,
            "usable_canopy_km2": 0.0,
            "usable_canopy_meets_minimum": False,
        },
    }


def _report(
    own, resources, overlap, tile_size, region, reads, perimeters, result
) -> dict[str, Any]:
    return {
        "run_utc": datetime.now(UTC).isoformat(),
        "resources": resources,
        "region_searched": list(region),
        "overlap": overlap,
        "tiles": _tile_summary(tile_size, result["tiles"]["candidates"]),
        "reads": reads,
        "fires_in_gap": [
            {k: v for k, v in fire.items() if k != "geometry"} for fire in perimeters
        ],
        "pair": result,
        "answer": {
            "shared_km2_upper_bound": overlap["shared_km2"],
            "shared_in_study_box_km2": overlap["shared_in_study_box_km2"],
            "distance_to_study_box_km": overlap["shared_distance_to_study_box_km"],
            "valid_both_tiles": result["tiles"]["valid_both"],
            "usable_canopy_km2": result["usable_canopy_km2"],
            "usable_canopy_min_km2": result["usable_canopy_min_km2"],
            "usable_canopy_meets_minimum": result["usable_canopy_meets_minimum"],
        },
    }
