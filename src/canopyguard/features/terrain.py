"""Static 3DEP terrain features aligned to the existing 10 m LiDAR label cells."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from scipy.signal import fftconvolve

from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import (
    file_sha256,
    read_provenance,
    sidecar_path,
    study_area_box,
    write_provenance,
)

CELL_ID_ROW_BASE = 10_000_000


def _target_grid(box: tuple, crs: str, resolution: int, padding: int):
    """Cover the study box and a full TPI neighbourhood on a global grid."""
    west, south, east, north = transform_bounds("EPSG:4326", crs, *box, densify_pts=21)
    left = math.floor((west - padding) / resolution) * resolution
    right = math.ceil((east + padding) / resolution) * resolution
    bottom = math.floor((south - padding) / resolution) * resolution
    top = math.ceil((north + padding) / resolution) * resolution
    shape = (int((top - bottom) / resolution), int((right - left) / resolution))
    return shape, from_origin(left, top, resolution, resolution)


def _warp_dem(path, box: tuple, settings: dict) -> tuple[np.ndarray, rasterio.Affine]:
    resolution = int(settings["resolution_m"])
    shape, transform = _target_grid(
        box, settings["target_crs"], resolution, int(settings["padding_m"])
    )
    elevation = np.full(shape, np.nan, dtype=np.float32)
    with rasterio.open(path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=elevation,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs=settings["target_crs"],
            dst_nodata=np.nan,
            resampling=Resampling[settings["resampling"]],
        )
    if not np.isfinite(elevation).any():
        raise ValueError("DEM has no valid elevation in the study box")
    return elevation, transform


def _slope_aspect(elevation: np.ndarray, resolution: float) -> tuple:
    """Slope and downslope azimuth, clockwise from north, on a metric grid."""
    south_gradient, east_gradient = np.gradient(elevation, resolution)
    slope = np.degrees(np.arctan(np.hypot(east_gradient, south_gradient)))
    aspect = np.degrees(np.arctan2(-east_gradient, south_gradient)) % 360
    slope = np.where(np.isfinite(elevation), slope, np.nan)
    aspect = np.where(np.isfinite(elevation), aspect, np.nan)
    return slope, aspect


def _heat_load(slope_deg: np.ndarray, aspect_deg: np.ndarray, lat_deg: np.ndarray):
    """McCune and Keon (2002), Eq. 1 with NE-SW folded aspect and erratum."""
    slope = np.radians(slope_deg)
    latitude = np.radians(lat_deg)
    folded = np.radians(np.abs(180 - np.abs(aspect_deg - 225)))
    log_index = (
        -1.467
        + 1.582 * np.cos(latitude) * np.cos(slope)
        - 1.5 * np.cos(folded) * np.sin(slope) * np.sin(latitude)
        - 0.262 * np.sin(latitude) * np.sin(slope)
        + 0.607 * np.sin(folded) * np.sin(slope)
    )
    return np.exp(log_index)


def _tpi(elevation: np.ndarray, resolution: float, radius: float) -> np.ndarray:
    """Center elevation minus a complete circular-neighbourhood mean."""
    cells = int(math.ceil(radius / resolution))
    offsets = np.arange(-cells, cells + 1) * resolution
    east, north = np.meshgrid(offsets, offsets)
    disk = ((east**2 + north**2) <= radius**2).astype(np.float32)
    valid = np.isfinite(elevation)
    sums = fftconvolve(np.where(valid, elevation, 0), disk, mode="same")
    counts = fftconvolve(valid.astype(np.float32), disk, mode="same")
    complete = counts >= disk.sum() - 0.5
    return np.where(valid & complete, elevation - sums / disk.sum(), np.nan)


def _sample_indices(
    ids: np.ndarray, x: np.ndarray, y: np.ndarray, transform, resolution: int
) -> tuple[np.ndarray, np.ndarray]:
    """Require 1:1 ID and centre alignment before sampling the warped DEM."""
    column = np.floor(x / resolution).astype(np.int64)
    row = np.floor(y / resolution).astype(np.int64)
    expected = column * CELL_ID_ROW_BASE + row
    if not np.array_equal(ids, expected) or len(np.unique(ids)) != len(ids):
        raise ValueError("LiDAR cell ID and grid centre do not align 1:1")
    cols = np.rint((x - transform.c) / resolution - 0.5).astype(np.int64)
    rows = np.rint((transform.f - y) / resolution - 0.5).astype(np.int64)
    if not (
        np.allclose(x, transform.c + (cols + 0.5) * resolution, atol=1e-5, rtol=0)
        and np.allclose(y, transform.f - (rows + 0.5) * resolution, atol=1e-5, rtol=0)
    ):
        raise ValueError("LiDAR centres are not aligned to the DEM grid")
    return rows, cols


def build_terrain_table(forecast: dict, study: dict, label_crs: str) -> dict:
    """Build static predictors; read only cell ID and centre from label table."""
    root = project_root()
    settings = forecast["stage2_residual_model"]["terrain"]
    if settings["target_crs"] != label_crs:
        raise ValueError("Terrain CRS must equal the LiDAR label CRS")
    if settings["padding_m"] < settings["tpi_radius_m"]:
        raise ValueError("DEM padding must cover the TPI radius")
    dem = root / settings["dem_path"]
    source = root / forecast["stage1_growth_model"]["clean_screen"]["output_path"]
    dem_record = read_provenance(dem)
    read_provenance(source)
    cells = pd.read_parquet(source, columns=["cell_id", "x", "y"])
    ids, x, y = (cells[name].to_numpy() for name in ("cell_id", "x", "y"))
    box = study_area_box(study)
    elevation, transform = _warp_dem(dem, box, settings)
    rows, cols = _sample_indices(ids, x, y, transform, settings["resolution_m"])
    if (
        rows.min() < 0
        or cols.min() < 0
        or rows.max() >= elevation.shape[0]
        or cols.max() >= elevation.shape[1]
    ):
        raise ValueError("LiDAR cell lies outside buffered DEM grid")
    slope, aspect = _slope_aspect(elevation, settings["resolution_m"])
    tpi = _tpi(elevation, settings["resolution_m"], settings["tpi_radius_m"])
    _, latitude = Transformer.from_crs(
        label_crs, "EPSG:4326", always_xy=True
    ).transform(x, y)
    table = pd.DataFrame(
        {
            "cell_id": ids,
            "elevation_m": elevation[rows, cols],
            "slope_deg": slope[rows, cols],
            "heat_load": _heat_load(slope[rows, cols], aspect[rows, cols], latitude),
            "tpi_450": tpi[rows, cols],
        }
    )
    output = ensure_parent(root / settings["output_path"])
    table.to_parquet(output, index=False)
    sidecar = write_provenance(
        output,
        source_url=settings["dem_url"],
        script_name="build_terrain.py",
        bbox_wgs84=box,
        crs=label_crs,
        row_count=len(table),
    )
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    record["dem_sha256"] = dem_record["sha256"]
    record["clean_cells_sha256"] = file_sha256(source)
    record["resolution_m"] = settings["resolution_m"]
    record["tpi_radius_m"] = settings["tpi_radius_m"]
    record["padding_m"] = settings["padding_m"]
    sidecar_path(output).write_text(json.dumps(record, indent=2) + "\n", "utf-8")
    return {"cells": len(table), "complete": int(table.notna().all(axis=1).sum())}
