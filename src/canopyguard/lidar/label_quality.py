"""Select one valid label per global cell from overlapping LiDAR tiles."""

from __future__ import annotations

import hashlib
import json

import numpy as np
from numpy.typing import NDArray

from canopyguard.io import ensure_parent, project_root

REQUIRED = (
    "cell_id",
    "tile",
    "x",
    "y",
    "valid_start",
    "valid_end",
    "mean_change",
    "p95_change",
    "max_change",
)
CHANGE_KEYS = ("mean_change", "p95_change", "max_change")


def _valid_rows(table: dict[str, NDArray], min_valid: float) -> NDArray[np.int64]:
    if not 0 <= min_valid <= 1:
        raise ValueError("Minimum valid fraction must be between zero and one")
    missing = set(REQUIRED) - set(table)
    if missing:
        raise ValueError(f"Missing label columns: {', '.join(sorted(missing))}")
    count = len(table["cell_id"])
    if any(values.ndim != 1 or len(values) != count for values in table.values()):
        raise ValueError("Label columns must be one-dimensional and equal length")
    valid = (table["valid_start"] >= min_valid) & (table["valid_end"] >= min_valid)
    for key in CHANGE_KEYS:
        valid &= np.isfinite(table[key])
    return np.flatnonzero(valid)


def _duplicate_summary(
    table: dict[str, NDArray], ordered: NDArray[np.int64]
) -> tuple[dict, NDArray[np.int64]]:
    ids = table["cell_id"][ordered]
    _, starts, counts = np.unique(ids, return_index=True, return_counts=True)
    repeated = starts[counts > 1]
    lengths = counts[counts > 1]
    largest = {key: 0.0 for key in CHANGE_KEYS}
    disagreeing = 0
    disputed_ids = []
    for start, length in zip(repeated, lengths, strict=True):
        group = ordered[start : start + length]
        if np.unique(table["tile"][group]).size != length:
            raise ValueError("The same tile contains a repeated cell ID")
        if any(np.any(table[key][group] != table[key][group[0]]) for key in ("x", "y")):
            raise ValueError("A repeated cell ID has different coordinates")
        differences = {key: float(np.ptp(table[key][group])) for key in CHANGE_KEYS}
        if any(value > 0 for value in differences.values()):
            disagreeing += 1
            disputed_ids.append(ids[start])
        for key, value in differences.items():
            largest[key] = max(largest[key], value)
    return (
        {
            "duplicate_cell_ids": int(len(repeated)),
            "disagreeing_cell_ids": int(disagreeing),
            "max_change_disagreement_m": largest,
        },
        np.asarray(disputed_ids, dtype=np.int64),
    )


def select_unique_valid_labels(
    table: dict[str, NDArray], min_valid_fraction: float
) -> tuple[dict[str, NDArray], dict]:
    """Keep the best-covered observation, breaking ties by lower tile ID.

    The smaller of the two valid fractions is the primary coverage score so
    neither epoch can compensate for a poorly observed counterpart. The sum
    resolves equal minima. Tile ID is a stable last tie-breaker. The outcome
    value never determines which duplicate wins.
    """
    valid = _valid_rows(table, min_valid_fraction)
    minimum = np.minimum(table["valid_start"][valid], table["valid_end"][valid])
    total = table["valid_start"][valid] + table["valid_end"][valid]
    order = np.lexsort(
        (table["tile"][valid], -total, -minimum, table["cell_id"][valid])
    )
    ordered = valid[order]
    ids = table["cell_id"][ordered]
    first = np.r_[True, ids[1:] != ids[:-1]] if ids.size else np.array([], dtype=bool)
    chosen = ordered[first]
    summary, disputed_ids = _duplicate_summary(table, ordered)
    audit = {
        "raw_rows": int(len(table["cell_id"])),
        "valid_rows": int(len(valid)),
        "unique_valid_cells": int(len(chosen)),
        "removed_valid_overlap_rows": int(len(valid) - len(chosen)),
        "selection_rule": (
            "highest minimum epoch coverage, highest total coverage, lowest tile ID"
        ),
        **summary,
    }
    selected = {key: values[chosen] for key, values in table.items()}
    selected["overlap_disputed"] = np.isin(selected["cell_id"], disputed_ids)
    return selected, audit


def build_unique_archive(config: dict) -> dict:
    """Check the archived input hash and write unique labels plus an audit."""
    root = project_root()
    paths = config["label_archive"]
    source = root / paths["source"]
    with source.open("rb") as stream:
        source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if source_hash != paths["source_sha256"]:
        raise ValueError("Label archive hash differs from the configured source")
    with np.load(source, allow_pickle=False) as archive:
        table = {key: archive[key] for key in archive.files}
    unique, audit = select_unique_valid_labels(
        table, float(config["aggregation"]["min_valid_fraction"])
    )
    output = ensure_parent(root / paths["unique"])
    np.savez_compressed(output, **unique)
    with output.open("rb") as stream:
        output_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    audit["source_sha256"] = source_hash
    audit["unique_sha256"] = output_hash
    ensure_parent(root / paths["audit"]).write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    return audit
