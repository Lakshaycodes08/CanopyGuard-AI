"""Build independently screened 2013-2022 growth cells for issue 8."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from canopyguard.data.fire_perimeters import (
    fetch_study_features,
    file_hash,
    point_hits,
    projected_features,
)
from canopyguard.data.hansen import download_lossyear, loss_year_at_cells
from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import study_area_box, write_provenance


def wire_suspects(path: Path, cell_ids: np.ndarray) -> tuple[np.ndarray, bool]:
    """Join PR 13's optional suspect archive by cell ID, never row position."""
    result = np.zeros(len(cell_ids), dtype=bool)
    if not path.exists():
        return result, False
    with np.load(path, allow_pickle=False) as source:
        ids = source["cell_id"]
        flags = source["wire_suspect"]
    if len(ids) == 0:
        return result, True
    order = np.argsort(ids)
    sorted_ids = ids[order]
    position = np.searchsorted(sorted_ids, cell_ids)
    valid = position < len(sorted_ids)
    hit = valid & (sorted_ids[np.minimum(position, len(sorted_ids) - 1)] == cell_ids)
    result[hit] = flags[order[position[hit]]]
    return result, True


def clean_flags(
    labels: dict,
    vegetation: pd.DataFrame,
    burned: np.ndarray,
    hansen_loss: np.ndarray,
    hansen_valid: np.ndarray,
    near_line: np.ndarray,
    wire_suspect: np.ndarray,
    settings: dict,
) -> pd.DataFrame:
    """Apply the declared exclusions while retaining every audit flag."""
    if not np.array_equal(labels["cell_id"], vegetation["cell_id"].to_numpy()):
        raise ValueError("Vegetation and label cell IDs do not align")
    n = len(labels["cell_id"])
    arrays = (burned, hansen_loss, hansen_valid, near_line, wire_suspect)
    if any(len(values) != n for values in arrays):
        raise ValueError("Screen flags must align with labels")
    canopy = np.isfinite(labels["mean_start"]) & (
        labels["mean_start"] >= settings["min_mean_start_m"]
    )
    lidar_loss = np.isfinite(labels["loss_share"]) & (
        labels["loss_share"] >= settings["loss_share_threshold"]
    )
    named = vegetation["vegetation_type"].to_numpy() != "uncertain"
    line_or_wire = near_line | wire_suspect
    clean = (
        ~labels["overlap_disputed"]
        & canopy
        & named
        & hansen_valid
        & ~burned
        & ~hansen_loss
        & ~lidar_loss
        & ~line_or_wire
    )
    return pd.DataFrame(
        {
            "cell_id": labels["cell_id"],
            "x": labels["x"],
            "y": labels["y"],
            "vegetation_type": vegetation["vegetation_type"].to_numpy(),
            "broader_group": vegetation["broader_group"].to_numpy(),
            "model_group": vegetation["model_group"].to_numpy(),
            "overlap_disputed": labels["overlap_disputed"],
            "canopy_at_start": canopy,
            "vegetation_known": named,
            "burned_2013_2022": burned,
            "hansen_loss": hansen_loss,
            "hansen_valid": hansen_valid,
            "lidar_loss": lidar_loss,
            "near_line": line_or_wire,
            "wire_suspect": wire_suspect,
            "clean": clean,
        }
    )


def exclusion_counts(table: pd.DataFrame) -> dict:
    """Give both overlapping rule totals and sequential removal counts."""
    rules = {
        "overlap_disputed": table["overlap_disputed"].to_numpy(),
        "no_2013_canopy": ~table["canopy_at_start"].to_numpy(),
        "vegetation_uncertain": ~table["vegetation_known"].to_numpy(),
        "hansen_nodata": ~table["hansen_valid"].to_numpy(),
        "burned_2013_2022": table["burned_2013_2022"].to_numpy(),
        "hansen_loss": table["hansen_loss"].to_numpy(),
        "lidar_loss": table["lidar_loss"].to_numpy(),
        "near_line": table["near_line"].to_numpy(),
    }
    eligible = np.ones(len(table), dtype=bool)
    sequential = {}
    for name, excluded in rules.items():
        sequential[name] = int((eligible & excluded).sum())
        eligible &= ~excluded
    if not np.array_equal(eligible, table["clean"].to_numpy()):
        raise ValueError("Exclusion counts do not reproduce the clean mask")
    return {
        "all_cells": len(table),
        "rule_totals": {name: int(values.sum()) for name, values in rules.items()},
        "sequential_removed": sequential,
        "clean_cells": int(eligible.sum()),
        "clean_by_type": table.loc[eligible, "vegetation_type"]
        .value_counts()
        .to_dict(),
        "clean_by_group": table.loc[eligible, "broader_group"].value_counts().to_dict(),
    }


def _source_paths(root: Path, settings: dict, bbox: dict) -> dict:
    paths = {}
    for name in ("frap", "mtbs", "cec"):
        source = settings["sources"][name]
        path = root / source["path"]
        count = fetch_study_features(source["url"], bbox, source["where"], path)
        paths[name] = {"path": path, "count": count}
    hansen = settings["sources"]["hansen"]
    path = root / hansen["path"]
    download_lossyear(hansen["url"], path)
    paths["hansen"] = {"path": path}
    return paths


def build_clean_cells(forecast: dict, study: dict) -> dict:
    """Fetch source evidence, apply masks, and save Parquet plus provenance."""
    root = project_root()
    settings = forecast["clean_screen"]
    bbox = study["study_area"]["bbox"]
    paths = _source_paths(root, settings, bbox)
    with np.load(root / forecast["labels_path"], allow_pickle=False) as archive:
        labels = {key: archive[key] for key in archive.files}
    vegetation = pd.read_parquet(root / forecast["vegetation_join"]["output_path"])
    x, y = labels["x"], labels["y"]
    chunk_size = int(settings["chunk_size"])
    fires = [
        item
        for name in ("frap", "mtbs")
        for item in projected_features(paths[name]["path"])
    ]
    burned = point_hits(x, y, [geometry for geometry, _ in fires], chunk_size)
    lines = projected_features(paths["cec"]["path"])
    buffered = [
        geometry.buffer(float(settings["near_line_m"])) for geometry, _ in lines
    ]
    near_line = point_hits(x, y, buffered, chunk_size)
    first_year, last_year = settings["fire_years"]
    hansen_loss, hansen_valid = loss_year_at_cells(
        paths["hansen"]["path"], x, y, first_year, last_year
    )
    suspects, wire_available = wire_suspects(
        root / settings["wire_flags_path"], labels["cell_id"]
    )
    table = clean_flags(
        labels,
        vegetation,
        burned,
        hansen_loss,
        hansen_valid,
        near_line,
        suspects,
        settings,
    )
    bbox = study_area_box(study)
    for name, item in paths.items():
        source_path = item["path"]
        source_bbox = (-130.0, 30.0, -120.0, 40.0) if name == "hansen" else bbox
        write_provenance(
            source_path,
            source_url=settings["sources"][name]["url"],
            script_name="build_clean_cells.py",
            bbox_wgs84=source_bbox,
            crs="EPSG:4326",
            row_count=item.get("count"),
        )
    output = ensure_parent(root / settings["output_path"])
    table.to_parquet(output, index=False)
    write_provenance(
        output,
        source_url="https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8",
        script_name="build_clean_cells.py",
        bbox_wgs84=bbox,
        crs="EPSG:6339",
        row_count=len(table),
    )
    summary = exclusion_counts(table)
    summary["sources"] = {
        name: {
            "url": settings["sources"][name]["url"],
            "path": str(item["path"].relative_to(root)),
            "sha256": file_hash(item["path"]),
            "raw_file_modified_utc": datetime.fromtimestamp(
                item["path"].stat().st_mtime, UTC
            ).isoformat(),
            "features": item.get("count"),
        }
        for name, item in paths.items()
    }
    summary["fire_names"] = sorted(
        {
            str(props.get("FIRE_NAME") or props.get("fire_name") or "")
            for _, props in fires
        }
    )
    summary["wire_flags_available"] = wire_available
    summary["screen_generated_utc"] = datetime.now(UTC).isoformat()
    summary["study_bbox"] = bbox
    summary["settings"] = settings
    ensure_parent(output.with_suffix(".provenance.json")).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
