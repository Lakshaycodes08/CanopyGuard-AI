"""The fixed E8 label and wire-quality population."""

from __future__ import annotations

import numpy as np


def quality_mask(labels: dict, flags: dict) -> tuple[np.ndarray, dict]:
    """Apply only preregistered overlap, p95, and wire exclusions."""
    ids = labels["cell_id"]
    undisputed = ~labels["overlap_disputed"]
    flag_order = np.argsort(flags["cell_id"])
    flag_ids = flags["cell_id"][flag_order]
    if len(np.unique(flag_ids)) != len(flag_ids):
        raise ValueError("Wire flag archive contains duplicate cell IDs")
    positions = np.searchsorted(flag_ids, ids[undisputed])
    if np.any(positions >= len(flag_ids)) or not np.array_equal(
        flag_ids[positions], ids[undisputed]
    ):
        raise ValueError("Every undisputed label must have a wire flag")
    wire_excluded = np.zeros(len(ids), dtype=bool)
    wire_excluded[undisputed] = flags["exclude_max_p95"][flag_order[positions]]
    finite = np.isfinite(labels["p95_end"])
    mask = undisputed & finite & ~wire_excluded
    counts = {
        "label_cells": len(ids),
        "disputed_overlap": int((~undisputed).sum()),
        "nonfinite_p95_after_overlap": int((undisputed & ~finite).sum()),
        "wire_excluded_after_overlap_and_p95": int(
            (undisputed & finite & wire_excluded).sum()
        ),
        "before_product_nodata": int(mask.sum()),
    }
    return mask, counts


def join_vegetation(cell_ids: np.ndarray, vegetation) -> dict[str, np.ndarray]:
    """Join 2013 map classes to every LiDAR cell by unique cell ID."""
    map_ids = vegetation["cell_id"].to_numpy()
    if len(np.unique(map_ids)) != len(map_ids):
        raise ValueError("2013 vegetation table contains duplicate cell IDs")
    order = np.argsort(map_ids)
    if len(map_ids) != len(cell_ids) or not np.array_equal(
        map_ids[order], np.sort(cell_ids)
    ):
        raise ValueError("2013 vegetation table must cover every LiDAR cell")
    positions = np.searchsorted(map_ids[order], cell_ids)
    return {
        name: vegetation[name].to_numpy()[order][positions]
        for name in ("vegetation_type", "broader_group")
    }
