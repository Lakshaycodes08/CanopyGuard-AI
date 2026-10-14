"""Wire suspect flags and the near-line exclusion for max and p95 labels.

A cell is a wire suspect when it is flagged as an isolated tall return in
either epoch within the near band. Cells within the exclusion distance of a
mapped line are also dropped from maximum and 95th-percentile analyses,
because the excess of spikes sits right at the line. Mean-based labels are
not affected. Research label quality control, not a clearance assessment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from canopyguard.lidar.wire_check import analysis_rows
from canopyguard.lidar.wire_check_run import (
    epoch_flags,
    line_distance,
    suspect_mask,
)


def file_sha256(path: str) -> str:
    """SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_flags(
    table: dict[str, NDArray], cfg: dict[str, Any], lines_path: str
) -> tuple[dict[str, NDArray], dict[str, Any]]:
    """Per-cell flag arrays for the analysed cells, and the counts summary."""
    rows, disputed_removed = analysis_rows(table)
    dist = line_distance(lines_path, table["x"][rows], table["y"][rows])
    flags = {e: epoch_flags(table, rows, e, cfg) for e in cfg["epochs"]}
    suspect = suspect_mask(flags, dist, cfg["bands_m"]["near"][1])
    within = dist < cfg["exclusion"]["within_line_m"]
    excluded = suspect | within
    arrays = {
        "cell_id": table["cell_id"][rows],
        "dist_to_line_m": dist.astype(np.float32),
        "wire_suspect": suspect,
        "within_exclusion_m": within,
        "exclude_max_p95": excluded,
    }
    return arrays, remaining_counts(table, rows, arrays, cfg, disputed_removed)


def remaining_counts(
    table: dict[str, NDArray],
    rows: NDArray,
    arrays: dict[str, NDArray],
    cfg: dict[str, Any],
    disputed_removed: int,
) -> dict[str, Any]:
    """How many cells are flagged and how many remain for modelling."""
    suspect, within = arrays["wire_suspect"], arrays["within_exclusion_m"]
    excluded = arrays["exclude_max_p95"]
    with np.errstate(invalid="ignore"):
        canopy = (
            table["mean_start"][rows] >= cfg["exclusion"]["modelling_min_mean_start_m"]
        )
    return {
        "analysed_cells": len(rows),
        "disputed_removed": disputed_removed,
        "wire_suspect": int(suspect.sum()),
        "within_exclusion_distance": int(within.sum()),
        "both": int((suspect & within).sum()),
        "excluded_from_max_p95": int(excluded.sum()),
        "remaining_for_mean_labels": len(rows),
        "remaining_for_max_p95": int((~excluded).sum()),
        "canopy_cells_before": int(canopy.sum()),
        "canopy_cells_remaining_for_max_p95": int((canopy & ~excluded).sum()),
    }


def apply_max_p95_exclusion(
    table: dict[str, NDArray], flag_table: dict[str, NDArray], columns: list[str]
) -> dict[str, NDArray]:
    """Copy of the label table with excluded cells set to NaN in max and p95."""
    excluded_ids = flag_table["cell_id"][flag_table["exclude_max_p95"]]
    hit = np.isin(table["cell_id"], excluded_ids)
    out = dict(table)
    for name in columns:
        out[name] = np.where(hit, np.nan, table[name].astype(np.float64))
    return out


def run_flags(cfg: dict[str, Any]) -> dict[str, Any]:
    """Write the flag archive and a summary with counts and input hashes."""
    table = dict(np.load(cfg["labels_path"]))
    arrays, counts = build_flags(table, cfg, cfg["lines_path"])
    flags_path = Path(cfg["flags_path"])
    flags_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(flags_path, **arrays)
    summary = {
        "counts": counts,
        "rule": {
            "spike": cfg["spike"],
            "near_band_m": cfg["bands_m"]["near"],
            "exclusion": cfg["exclusion"],
        },
        "inputs": {
            "labels_sha256": file_sha256(cfg["labels_path"]),
            "lines_sha256": file_sha256(cfg["lines_path"]),
            "lines_source_url": cfg["lines_source_url"],
        },
    }
    Path(cfg["flags_summary_path"]).write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
