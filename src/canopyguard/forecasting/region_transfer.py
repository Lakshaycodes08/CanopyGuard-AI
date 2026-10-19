"""Leave-one-region-out tables for testing whether a model transfers.

Regions adjoin each other, so test rows within a buffer of another region are
excluded from scoring; otherwise neighbouring pixels would leak across the
boundary.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

CLASS_PREFIXES = ("eco_", "veg_", "lf_")


def stack_regions(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Concatenate region tables; a class absent from a region is zero there."""
    columns = sorted({c for t in tables.values() for c in t.columns})
    parts = []
    for name, table in tables.items():
        part = table.copy()
        for column in columns:
            if column not in part.columns:
                part[column] = 0.0 if column.startswith(CLASS_PREFIXES) else np.nan
        part["region"] = name
        parts.append(
            part[[*columns, "region"]].drop(columns=["region"]).assign(region=name)
        )
    return pd.concat(parts, ignore_index=True)


def utm_box(bbox_wgs84: tuple[float, float, float, float], crs: str) -> tuple:
    """Axis-aligned UTM box around a longitude and latitude box."""
    from pyproj import Transformer

    west, south, east, north = bbox_wgs84
    project = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    x, y = project([west, west, east, east], [south, north, south, north])
    return float(min(x)), float(min(y)), float(max(x)), float(max(y))


def distance_to_box(
    easting: NDArray, northing: NDArray, box: tuple[float, float, float, float]
) -> NDArray[np.float64]:
    """Distance in metres to a rectangle; zero inside it."""
    min_x, min_y, max_x, max_y = box
    dx = np.maximum.reduce([min_x - easting, np.zeros_like(easting), easting - max_x])
    dy = np.maximum.reduce(
        [min_y - northing, np.zeros_like(northing), northing - max_y]
    )
    return np.hypot(dx, dy)


def far_from_other_regions(
    table: pd.DataFrame, boxes: dict[str, tuple], buffer_m: float
) -> NDArray[np.bool_]:
    """True where a row is at least `buffer_m` from every other region's box."""
    keep = np.ones(len(table), dtype=bool)
    easting = table["x"].to_numpy()
    northing = table["y"].to_numpy()
    for name, box in boxes.items():
        other = (table["region"] != name).to_numpy()
        keep &= ~(other & (distance_to_box(easting, northing, box) < buffer_m))
    return keep


def region_codes(table: pd.DataFrame, names: list[str]) -> NDArray[np.int64]:
    """Integer fold per row, one fold per region."""
    unknown = set(table["region"]) - set(names)
    if unknown:
        msg = f"Regions not in the configured list: {sorted(unknown)}"
        raise KeyError(msg)
    return table["region"].map({n: i for i, n in enumerate(names)}).to_numpy(np.int64)


def apply_screen(table: pd.DataFrame, rule: dict[str, float]) -> pd.DataFrame:
    """Keep rows that satisfy the screen; an empty rule keeps everything."""
    keep = np.ones(len(table), dtype=bool)
    if "max_burned_share" in rule:
        keep &= (table["burned"] <= rule["max_burned_share"]).to_numpy()
    if "max_loss_share" in rule:
        keep &= (table["loss_share"] <= rule["max_loss_share"]).to_numpy()
    return table[keep]


def class_summary(table: pd.DataFrame, config: dict[str, Any]) -> dict[str, float]:
    """Mean change and canopy share per region, for the report."""
    grouped = table.groupby("region")
    return {
        name: {
            "rows": int(len(g)),
            "mean_change": float(g["mean_change"].mean()),
            "p95_start_mean": float(g["p95_start"].mean()),
        }
        for name, g in grouped
    }
