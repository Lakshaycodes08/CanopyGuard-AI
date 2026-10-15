"""Run the wire and tower label check for one label archive and line file."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import unary_union

from canopyguard.lidar.wire_check import (
    analysis_rows,
    expected_counts,
    flag_spikes,
    neighbour_median,
    strata_keys,
    tile_bootstrap_ratio,
    to_grid,
)


def line_union(lines_path: str):
    """All mapped lines as one geometry in EPSG:6339."""
    project = Transformer.from_crs(4326, 6339, always_xy=True).transform
    features = json.loads(Path(lines_path).read_text(encoding="utf-8"))["features"]
    lines = [
        shapely.transform(
            shape(f["geometry"]),
            lambda c: np.column_stack(project(c[:, 0], c[:, 1])),
        )
        for f in features
    ]
    return unary_union(lines)


def line_distance(lines_path: str, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Distance in metres from each cell centre to the nearest mapped line."""
    return shapely.distance(shapely.points(x, y), line_union(lines_path))


def epoch_flags(table: dict, rows: np.ndarray, epoch: str, cfg: dict) -> dict:
    """Spike flags and eligibility for every analysed cell in one epoch."""
    x, y = table["x"][rows], table["y"][rows]
    top = table[f"max_{epoch}"][rows]
    upper = table[f"p95_{epoch}"][rows]
    grid, column, row = to_grid(x, y, top, cfg["cell_m"])
    around = neighbour_median(grid, column, row, cfg["spike"]["min_neighbours"])
    valid = table["valid_start" if epoch == "start" else "valid_end"][rows]
    isolated, wire_like = flag_spikes(top, upper, around, cfg["spike"])
    eligible = (
        np.isfinite(top) & np.isfinite(around) & (valid >= cfg["min_valid_fraction"])
    )
    return {
        "isolated": isolated & eligible,
        "wire_like": wire_like & eligible,
        "eligible": eligible,
        "top": top,
        "upper": upper,
        "valid": valid,
    }


def band_result(flags: dict, name: str, dist: np.ndarray, tile, key, cfg) -> dict:
    """Ratio against matched controls for one distance band and one flag."""
    low, high = cfg["bands_m"][name]
    near = flags["eligible"] & (dist >= low) & (dist < high)
    control = flags["eligible"] & (dist > cfg["control_min_distance_m"])
    out = {"near_cells": int(near.sum()), "control_cells": int(control.sum())}
    for label in ("isolated", "wire_like"):
        flag = flags[label].astype(float)
        obs, exp, used = expected_counts(key, flag, near, control)
        size = key.max() + 1
        tile_of = np.zeros(size, dtype=np.int64)
        tile_of[key] = tile
        ratio, lo, hi = tile_bootstrap_ratio(
            tile_of,
            obs,
            exp,
            cfg["bootstrap_reps"],
            cfg["pass_rule"]["confidence"],
            cfg["seed"],
        )
        out[label] = {
            "near_flagged_raw": int(flag[near].sum()),
            "near_rate_raw": float(flag[near].mean()) if near.any() else None,
            "control_rate_raw": float(flag[control].mean()),
            "matched_near_cells": int(used.sum()),
            "observed": float(obs.sum()),
            "expected": float(exp.sum()),
            "ratio": ratio,
            "ci_low": lo,
            "ci_high": hi,
        }
    return out


def distance_profile(flags: dict, dist: np.ndarray, edges: list[float]) -> list[dict]:
    """Raw flag rate by distance bin, descriptive only."""
    rows = []
    for low, high in itertools.pairwise(edges):
        use = flags["eligible"] & (dist >= low) & (dist < high)
        rows.append(
            {
                "from_m": low,
                "to_m": high,
                "cells": int(use.sum()),
                "isolated_rate": float(flags["isolated"][use].mean())
                if use.any()
                else None,
                "wire_like_rate": float(flags["wire_like"][use].mean())
                if use.any()
                else None,
            }
        )
    return rows


def suspect_mask(flags: dict, dist: np.ndarray, near_upper_m: float) -> np.ndarray:
    """Cells inside the near band that are flagged isolated in either epoch."""
    either = flags["start"]["isolated"] | flags["end"]["isolated"]
    return (dist < near_upper_m) & either


def run(cfg: dict, labels_path: str, lines_path: str) -> dict:
    """All results for both epochs as a plain dictionary."""
    table = dict(np.load(labels_path))
    rows, disputed_removed = analysis_rows(table)
    dist = line_distance(lines_path, table["x"][rows], table["y"][rows])
    tile = table["tile"][rows]
    results = {"cells": len(rows), "disputed_removed": disputed_removed}
    cache = {}
    for epoch in cfg["epochs"]:
        flags = epoch_flags(table, rows, epoch, cfg)
        key = strata_keys(tile, table["canopy_share"][rows], flags["valid"], cfg)
        cache[epoch] = flags
        results[epoch] = {
            "eligible_cells": int(flags["eligible"].sum()),
            "isolated_total": int(flags["isolated"].sum()),
            "wire_like_total": int(flags["wire_like"].sum()),
            "bands": {
                name: band_result(flags, name, dist, tile, key, cfg)
                for name in cfg["bands_m"]
            },
            "profile": distance_profile(flags, dist, cfg["profile_edges_m"]),
        }
    mask = suspect_mask(cache, dist, cfg["bands_m"]["near"][1])
    results["proposed_mask_cells"] = int(mask.sum())
    results["_arrays"] = {"rows": rows, "dist": dist, "flags": cache, "mask": mask}
    return results
