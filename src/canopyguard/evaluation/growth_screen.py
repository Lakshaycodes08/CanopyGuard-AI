"""Selection and wire exclusions for the issue 8 growth comparisons."""

from __future__ import annotations

import numpy as np
import pandas as pd


def wire_exclusion(cell_ids: np.ndarray, archive: dict, within_m: float) -> dict:
    """Join PR 13 flags by ID and fail if an eligible cell lacks a flag."""
    ids = np.asarray(archive["cell_id"])
    if len(ids) == 0 and len(cell_ids) > 0:
        raise ValueError("Wire flag archive is empty")
    if len(cell_ids) == 0:
        empty = np.zeros(0, dtype=bool)
        return {"wire_suspect": empty, "within_line": empty, "excluded": empty}
    if len(np.unique(ids)) != len(ids):
        raise ValueError("Wire flag archive has duplicate cell IDs")
    order = np.argsort(ids)
    sorted_ids = ids[order]
    positions = np.searchsorted(sorted_ids, cell_ids)
    found = positions < len(sorted_ids)
    found &= sorted_ids[np.minimum(positions, len(sorted_ids) - 1)] == cell_ids
    if not found.all():
        raise ValueError("Eligible growth cell is missing from wire flag archive")
    rows = order[positions]
    suspect = np.asarray(archive["wire_suspect"])[rows]
    within = np.asarray(archive["dist_to_line_m"])[rows] < within_m
    return {
        "wire_suspect": suspect,
        "within_line": within,
        "excluded": suspect | within,
    }


def selection_masks(table: pd.DataFrame, settings: dict) -> dict[str, np.ndarray]:
    """Construct loss-on and loss-off screens from independent audit flags."""
    excluded = table["vegetation_type"].isin(settings["excluded_map_classes"])
    excluded |= table["broader_group"].eq("grass")
    base = (
        ~table["overlap_disputed"].to_numpy()
        & table["label_change_valid"].to_numpy()
        & table["canopy_at_start"].to_numpy()
        & table["vegetation_known"].to_numpy()
        & table["hansen_valid"].to_numpy()
        & ~table["burned_2013_2022"].to_numpy()
        & ~table["hansen_loss"].to_numpy()
        & ~table["near_line"].to_numpy()
        & ~excluded.to_numpy()
        & ~table["p95_wire_excluded"].to_numpy()
    )
    forest = table["broader_group"].isin(settings["forest_groups"]).to_numpy()
    return {
        "all_loss_off": base,
        "all_loss_on": base & ~table["lidar_loss"].to_numpy(),
        "forest_loss_off": base & forest,
        "forest_loss_on": base & forest & ~table["lidar_loss"].to_numpy(),
    }


def saturation_shares(
    frame: pd.DataFrame, start: np.ndarray, heights: dict
) -> dict[str, dict]:
    """Measure the fraction frozen at each proposed literature ceiling."""
    result = {}
    names = frame["vegetation_type"].to_numpy()
    for name in np.unique(names):
        use = names == name
        ceiling = heights.get(name)
        result[name] = {
            "cells": int(use.sum()),
            "A_m": ceiling,
            "at_or_above_A": None
            if ceiling is None
            else int((start[use] >= ceiling).sum()),
            "share": None if ceiling is None else float((start[use] >= ceiling).mean()),
        }
    return result


def fold_saturation_shares(
    frame: pd.DataFrame, start: np.ndarray, fold_a: np.ndarray
) -> dict[str, dict]:
    """Report held-out start heights reaching their training-derived A."""
    result = {}
    names = frame["vegetation_type"].to_numpy()
    for name in np.unique(names):
        use = names == name
        result[name] = {
            "cells": int(use.sum()),
            "A_min_m": float(fold_a[use].min()),
            "A_max_m": float(fold_a[use].max()),
            "at_or_above_A": int((start[use] >= fold_a[use]).sum()),
            "share": float((start[use] >= fold_a[use]).mean()),
        }
    return result
