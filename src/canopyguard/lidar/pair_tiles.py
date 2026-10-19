"""Usable canopy where two LiDAR epochs both hold returns, tile by tile.

Heights are the coarse above-ground heights of `tile_stats`. They separate
canopy from open ground and show large loss, but they are not a replacement for
the matched canopy height model used to measure change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from canopyguard.lidar import tile_stats
from canopyguard.lidar.tile_stats import TileGrid, TileStats


@dataclass(frozen=True)
class PairRules:
    """Thresholds for judging a tile pair."""

    min_cell_fraction: float
    min_ground_fraction: float
    canopy_min_m: float
    disturbance_limit_m: float
    height_classes_m: tuple[float, ...]
    slope_bands_deg: tuple[tuple[float, float], ...]
    cell_m: float


def _cell_masks(
    earlier: TileStats, later: TileStats, rules: PairRules, burned: np.ndarray
) -> dict[str, np.ndarray]:
    valid = {
        name: tile_stats.tile_validity(
            stats, rules.min_cell_fraction, rules.min_ground_fraction
        )
        for name, stats in (("earlier", earlier), ("later", later))
    }
    both = valid["earlier"]["valid"] & valid["later"]["valid"]
    height_early = tile_stats.heights_above_ground(earlier)
    height_late = tile_stats.heights_above_ground(later)
    ok = both[:, None, None] & np.isfinite(height_early) & np.isfinite(height_late)
    change = height_late - height_early
    canopy_both = (
        ok & (height_early >= rules.canopy_min_m) & (height_late >= rules.canopy_min_m)
    )
    lost = (
        ok
        & (height_early >= rules.canopy_min_m)
        & (change < -rules.disturbance_limit_m)
    )
    undisturbed = canopy_both & ~lost
    return {
        "validity": valid,
        "both": both,
        "ok": ok,
        "height_late": height_late,
        "change": change,
        "canopy_either": ok
        & ((height_early >= rules.canopy_min_m) | (height_late >= rules.canopy_min_m)),
        "canopy_both": canopy_both,
        "lost": lost,
        "undisturbed": undisturbed,
        "unburned_undisturbed": undisturbed & ~burned,
        "burned_canopy": canopy_both & burned,
    }


def _class_labels(edges: tuple[float, ...]) -> list[str]:
    labels = [
        f"{low:g}-{high:g} m" for low, high in zip(edges[:-1], edges[1:], strict=True)
    ]
    return [*labels, f"{edges[-1]:g} m and above"]


def _canopy_mix(
    height: np.ndarray, mask: np.ndarray, rules: PairRules
) -> dict[str, float]:
    area = (rules.cell_m / 1000.0) ** 2
    index = np.digitize(height[mask], rules.height_classes_m) - 1
    counts = np.bincount(index, minlength=len(rules.height_classes_m))
    return {
        label: float(count * area)
        for label, count in zip(
            _class_labels(rules.height_classes_m), counts, strict=True
        )
    }


def _terrain_mix(later: TileStats, ok: np.ndarray, rules: PairRules) -> dict[str, Any]:
    ground = tile_stats.ground_surface(later)
    slope = tile_stats.slope_degrees(ground, rules.cell_m)
    known = ok & np.isfinite(slope)
    area = (rules.cell_m / 1000.0) ** 2
    bands = {
        f"{low:g}-{high:g} deg": float(
            ((slope >= low) & (slope < high) & known).sum() * area
        )
        for low, high in rules.slope_bands_deg
    }
    elevation = ground[ok & np.isfinite(ground)]
    return {
        "slope_band_km2": bands,
        "median_slope_deg": float(np.median(slope[known])) if known.any() else None,
        "ground_elevation_m": (
            [
                float(np.min(elevation)),
                float(np.median(elevation)),
                float(np.max(elevation)),
            ]
            if elevation.size
            else None
        ),
    }


def _tile_rows(grid: TileGrid, masks: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    keys = ("canopy_both", "undisturbed", "lost", "burned_canopy")
    return [
        {
            "id": index,
            "bounds": list(tile),
            "valid_earlier": bool(masks["validity"]["earlier"]["valid"][index]),
            "valid_later": bool(masks["validity"]["later"]["valid"][index]),
            "cell_fraction_earlier": float(
                masks["validity"]["earlier"]["cell_fraction"][index]
            ),
            "cell_fraction_later": float(
                masks["validity"]["later"]["cell_fraction"][index]
            ),
            **{f"{key}_cells": int(masks[key][index].sum()) for key in keys},
        }
        for index, tile in enumerate(grid.tiles)
    ]


AREA_MASKS = (
    "canopy_either",
    "canopy_both",
    "lost",
    "undisturbed",
    "unburned_undisturbed",
    "burned_canopy",
)


def _areas_km2(masks: dict[str, np.ndarray], rules: PairRules) -> dict[str, float]:
    area = (rules.cell_m / 1000.0) ** 2
    result = {"valid_both_cells": float(masks["ok"].sum() * area)}
    result.update({name: float(masks[name].sum() * area) for name in AREA_MASKS})
    return result


def _change_summary(masks: dict[str, np.ndarray]) -> dict[str, float] | None:
    changes = masks["change"][masks["undisturbed"]]
    if not changes.size:
        return None
    return {
        "median": float(np.median(changes)),
        "p10": float(np.percentile(changes, 10)),
        "p90": float(np.percentile(changes, 90)),
        "cells": int(changes.size),
    }


def analyse_pair(
    grid: TileGrid,
    earlier: TileStats,
    later: TileStats,
    rules: PairRules,
    burned: np.ndarray,
    usable_canopy_min_km2: float,
) -> dict[str, Any]:
    """Areas of valid ground and canopy, their mix, and the go/no-go number."""
    masks = _cell_masks(earlier, later, rules, burned)
    areas = _areas_km2(masks, rules)
    usable = areas["unburned_undisturbed"]
    validity = masks["validity"]
    return {
        "tiles": {
            "candidates": len(grid.tiles),
            "valid_earlier": int(validity["earlier"]["valid"].sum()),
            "valid_later": int(validity["later"]["valid"].sum()),
            "valid_both": int(masks["both"].sum()),
        },
        "area_km2": areas,
        "usable_canopy_km2": usable,
        "usable_canopy_min_km2": usable_canopy_min_km2,
        "usable_canopy_meets_minimum": usable >= usable_canopy_min_km2,
        "canopy_height_class_km2": _canopy_mix(
            masks["height_late"], masks["canopy_both"], rules
        ),
        "terrain": _terrain_mix(later, masks["ok"], rules),
        "lidar_height_change_m_on_undisturbed": _change_summary(masks),
        "tile_rows": _tile_rows(grid, masks),
    }
