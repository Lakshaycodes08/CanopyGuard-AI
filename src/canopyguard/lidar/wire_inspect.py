"""Summarise raw LiDAR points inside suspect label cells.

Reads each cell from the public 3DEP Entwine store for both epochs and records
what the tallest return is: its class, how many points lie beneath it, and how
many wire (14) or tower (15) points the cell holds. A wire or pole is a thin
object with little beneath it; a tree has a dense column. Needs python-pdal and
network access. Research label quality check, not a clearance assessment.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import Transformer

from canopyguard.lidar.ept import EPT_BASE, to_web_mercator

FIELDS = [
    "group",
    "flag_epoch",
    "cell_id",
    "tile",
    "dist_to_line_m",
    "epoch",
    "points_in_cell",
    "points_in_window",
    "ground_points_in_window",
    "class_counts_in_cell",
    "wire_points_class14",
    "tower_points_class15",
    "apex_height_m",
    "apex_class",
    "apex_return",
    "apex_of_returns",
    "points_below_apex_2m",
    "points_above_5m_in_cell",
    "second_highest_m",
    "status",
]


def projects_for(lidar_config: dict[str, Any], epoch: str) -> tuple[list[str], float]:
    """Dataset names and the vertical scale to metres for one epoch."""
    for entry in lidar_config["epochs"]:
        if str(entry["name"]) == epoch:
            names = entry.get("datasets") or [entry["dataset"]]
            return list(names), float(entry.get("z_to_metres", 1.0))
    raise KeyError(f"Epoch {epoch} is not in the LiDAR config")


def read_window(
    project: str,
    center: tuple[float, float],
    window_m: float,
    z_to_metres: float,
    to_lonlat: Transformer,
) -> dict[str, np.ndarray] | None:
    """Raw points in a square window around a cell centre, in EPSG:6339."""
    import pdal

    cx, cy = center
    box = (cx - window_m, cy - window_m, cx + window_m, cy + window_m)
    corners = [to_lonlat.transform(box[0], box[1]), to_lonlat.transform(box[2], box[3])]
    (x0, y0), (x1, y1) = (to_web_mercator(*corner) for corner in corners)
    margin = 5.0
    spec = [
        {
            "type": "readers.ept",
            "filename": f"{EPT_BASE}/{project}/ept.json",
            "bounds": (
                f"([{min(x0, x1) - margin},{max(x0, x1) + margin}],"
                f"[{min(y0, y1) - margin},{max(y0, y1) + margin}])"
            ),
            "threads": 2,
        },
        {"type": "filters.reprojection", "out_srs": "EPSG:6339"},
        {
            "type": "filters.crop",
            "bounds": f"([{box[0]},{box[2]}],[{box[1]},{box[3]}])",
        },
    ]
    pipeline = pdal.Pipeline(json.dumps(spec))
    pipeline.execute()
    if not pipeline.arrays or len(pipeline.arrays[0]) == 0:
        return None
    arr = pipeline.arrays[0]
    return {
        "x": np.asarray(arr["X"], float),
        "y": np.asarray(arr["Y"], float),
        "z": np.asarray(arr["Z"], float) * z_to_metres,
        "cls": np.asarray(arr["Classification"], int),
        "rn": np.asarray(arr["ReturnNumber"], int),
        "nr": np.asarray(arr["NumberOfReturns"], int),
    }


def summarise(
    points: dict[str, np.ndarray], center: tuple[float, float], cfg: dict[str, Any]
) -> dict[str, Any]:
    """Metrics for one cell from raw points; pure numpy so it is testable."""
    cx, cy = center
    half = cfg["cell_m"] / 2.0
    in_cell = (np.abs(points["x"] - cx) <= half) & (np.abs(points["y"] - cy) <= half)
    ground = points["cls"] == 2
    out: dict[str, Any] = {
        "points_in_cell": int(in_cell.sum()),
        "points_in_window": len(points["x"]),
        "ground_points_in_window": int(ground.sum()),
    }
    if not in_cell.any():
        return {**out, "status": "no_points_in_cell"}
    if not ground.any():
        return {**out, "status": "no_ground_in_window"}
    height = points["z"] - float(np.median(points["z"][ground]))
    classes, counts = np.unique(points["cls"][in_cell], return_counts=True)
    out["class_counts_in_cell"] = ";".join(
        f"{c}:{n}" for c, n in zip(classes, counts, strict=True)
    )
    out["wire_points_class14"] = int(((points["cls"] == 14) & in_cell).sum())
    out["tower_points_class15"] = int(((points["cls"] == 15) & in_cell).sum())
    idx = np.flatnonzero(in_cell)
    top = idx[np.argmax(height[idx])]
    near_apex = (
        np.hypot(points["x"] - points["x"][top], points["y"] - points["y"][top])
        <= cfg["beneath_radius_m"]
    )
    beneath = near_apex & (height >= cfg["beneath_min_height_m"])
    beneath &= height <= height[top] - cfg["beneath_gap_m"]
    ordered = np.sort(height[idx])
    out.update(
        apex_height_m=round(float(height[top]), 2),
        apex_class=int(points["cls"][top]),
        apex_return=int(points["rn"][top]),
        apex_of_returns=int(points["nr"][top]),
        points_below_apex_2m=int(beneath.sum()),
        points_above_5m_in_cell=int((height[idx] >= 5.0).sum()),
        second_highest_m=round(float(ordered[-2]), 2) if len(idx) > 1 else "",
        status="ok",
    )
    return out


def inspect_cells(
    suspects_path: str,
    lidar_config: dict[str, Any],
    out_path: str,
    per_group: int,
) -> None:
    """Summarise every chosen suspect cell in both epochs; resumes on rerun."""
    cfg = lidar_config["wire_check"]["inspect"]
    to_lonlat = Transformer.from_crs(6339, 4326, always_xy=True)
    with open(suspects_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    taken: dict[tuple[str, str], int] = {}
    chosen = []
    for row in rows:
        key = (row["group"], row["epoch"])
        if taken.get(key, 0) < per_group:
            taken[key] = taken.get(key, 0) + 1
            chosen.append(row)
    out = Path(out_path)
    done: set[tuple[str, str, str]] = set()
    if out.exists():
        with open(out, newline="", encoding="utf-8") as handle:
            done = {
                (r["cell_id"], r["epoch"], r["flag_epoch"])
                for r in csv.DictReader(handle)
            }
    with open(out, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        if not done:
            writer.writeheader()
        for number, row in enumerate(chosen, start=1):
            center = (float(row["x_6339"]), float(row["y_6339"]))
            for epoch in cfg["epochs"]:
                if (row["cell_id"], epoch, row["epoch"]) in done:
                    continue
                result = _one_cell(lidar_config, cfg, epoch, center, to_lonlat)
                record = {
                    "group": row["group"],
                    "flag_epoch": row["epoch"],
                    "cell_id": row["cell_id"],
                    "tile": row["tile"],
                    "dist_to_line_m": row["dist_to_line_m"],
                    "epoch": epoch,
                    **result,
                }
                writer.writerow(record)
                handle.flush()
                print(
                    f"[{number}/{len(chosen)}] cell {row['cell_id']} {epoch}: {record['status']}"
                )
                time.sleep(cfg["pause_s"])


def _one_cell(lidar_config, cfg, epoch, center, to_lonlat) -> dict[str, Any]:
    projects, z_to_metres = projects_for(lidar_config, epoch)
    merged: dict[str, np.ndarray] | None = None
    status = "no_points"
    for project in projects:
        try:
            points = read_window(
                project, center, cfg["window_m"], z_to_metres, to_lonlat
            )
        except RuntimeError as error:
            status = f"read_error:{type(error).__name__}"
            continue
        if points is None:
            continue
        merged = (
            points
            if merged is None
            else {key: np.concatenate([merged[key], points[key]]) for key in points}
        )
    return summarise(merged, center, cfg) if merged else {"status": status}


def summarise_inspection(summary_path: str, thin_max_points: int) -> dict[str, Any]:
    """Shares of thin and tree-like tallest returns, by epoch and group.

    Only the epoch a cell was flagged in is used. A cell is thin when fewer
    than `thin_max_points` points lie beneath its tallest return.
    """
    with open(summary_path, newline="", encoding="utf-8") as handle:
        everything = list(csv.DictReader(handle))
    rows = [r for r in everything if r["status"] == "ok"]
    matched = {"start": "2013", "end": "2022"}
    result: dict[str, Any] = {"cell_epochs_not_read": len(everything) - len(rows)}
    for row in rows:
        if matched[row["flag_epoch"]] != row["epoch"]:
            continue
        key = f"{row['epoch']}_{row['group']}"
        item = result.setdefault(
            key, {"cells": 0, "thin": 0, "apex_class": {}, "below": [], "apex": []}
        )
        item["cells"] += 1
        item["thin"] += int(int(row["points_below_apex_2m"]) < thin_max_points)
        item["apex_class"][row["apex_class"]] = (
            item["apex_class"].get(row["apex_class"], 0) + 1
        )
        item["below"].append(int(row["points_below_apex_2m"]))
        item["apex"].append(float(row["apex_height_m"]))
        result["wire_class14_points"] = result.get("wire_class14_points", 0) + int(
            row["wire_points_class14"]
        )
        result["tower_class15_points"] = result.get("tower_class15_points", 0) + int(
            row["tower_points_class15"]
        )
    for key, item in list(result.items()):
        if isinstance(item, dict):
            item["thin_share"] = round(item["thin"] / item["cells"], 3)
            item["median_points_below"] = float(np.median(item.pop("below")))
            item["median_apex_m"] = round(float(np.median(item.pop("apex"))), 1)
    return result
