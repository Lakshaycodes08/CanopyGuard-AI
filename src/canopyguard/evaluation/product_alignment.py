"""Align retrospective product rasters to the existing LiDAR label cells."""

from __future__ import annotations

import numpy as np
import rasterio
from pyproj import proj_version_str
from pyproj.aoi import AreaOfInterest
from pyproj.transformer import TransformerGroup
from rasterio import Affine
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

from canopyguard.features.terrain import CELL_ID_ROW_BASE


def label_grid(cell_ids, x, y, resolution_m: int):
    """Build a raster on the measured global LiDAR grid and check every ID."""
    ids = np.asarray(cell_ids)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if resolution_m != 10:
        raise ValueError("ECHOSAT benchmark must use the existing 10 m label grid")
    if len(ids) == 0 or not (len(ids) == len(x) == len(y)):
        raise ValueError("Nonempty label IDs and centres must align")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Label centres must be finite")
    columns = np.floor(x / resolution_m).astype(np.int64)
    rows = np.floor(y / resolution_m).astype(np.int64)
    if not np.array_equal(ids, columns * CELL_ID_ROW_BASE + rows):
        raise ValueError("Label cell IDs do not match 10 m grid coordinates")
    if len(np.unique(ids)) != len(ids):
        raise ValueError("Label cell IDs must be unique")
    if not (
        np.allclose(x, (columns + 0.5) * resolution_m, atol=1e-5, rtol=0)
        and np.allclose(y, (rows + 0.5) * resolution_m, atol=1e-5, rtol=0)
    ):
        raise ValueError("Label centres do not lie on their cell grid")
    transform = from_origin(
        columns.min() * resolution_m,
        (rows.max() + 1) * resolution_m,
        resolution_m,
        resolution_m,
    )
    shape = (int(rows.max() - rows.min() + 1), int(columns.max() - columns.min() + 1))
    return transform, shape, rows.max() - rows, columns - columns.min()


def coordinate_operation(settings: dict, bbox: tuple[float, float, float, float]):
    """Require the pinned EPSG operation to be available for this study box."""
    group = TransformerGroup(
        settings["source_crs"],
        settings["target_crs"],
        always_xy=True,
        area_of_interest=AreaOfInterest(*bbox),
        allow_ballpark=False,
    )
    for candidate in group.transformers:
        if len(candidate.operations) < 2:
            continue
        operation = candidate.operations[1].to_json_dict()["id"]
        if (
            operation["code"] == settings["operation_epsg"]
            and candidate.to_proj4() == settings["operation_proj"]
            and candidate.accuracy == settings["operation_accuracy_m"]
        ):
            return candidate
    raise ValueError("Pinned ECHOSAT datum operation is unavailable or changed")


def align_echosat_band(
    source,
    band: int,
    cell_ids,
    x,
    y,
    label_crs: str,
    settings: dict,
    bbox: tuple[float, float, float, float],
    height_scale_to_m: float,
    offset_east_m: float = 0.0,
    offset_north_m: float = 0.0,
) -> tuple[np.ndarray, dict]:
    """Warp one ECHOSAT band onto label centres with the pinned operation."""
    if source.crs != rasterio.crs.CRS.from_string(settings["source_crs"]):
        raise ValueError("ECHOSAT source CRS differs from pinned benchmark CRS")
    if label_crs != settings["target_crs"]:
        raise ValueError("Benchmark target CRS differs from LiDAR label CRS")
    if source.nodata is None:
        raise ValueError("ECHOSAT source must declare nodata")
    transform, shape, rows, columns = label_grid(
        cell_ids, x, y, settings["resolution_m"]
    )
    operation = coordinate_operation(settings, bbox)
    destination = np.full(shape, np.nan, dtype=np.float32)
    shifted = Affine.translation(offset_east_m, offset_north_m) @ transform
    reproject(
        source=rasterio.band(source, band),
        destination=destination,
        src_transform=source.transform,
        src_crs=source.crs,
        src_nodata=source.nodata,
        dst_transform=shifted,
        dst_crs=settings["target_crs"],
        dst_nodata=np.nan,
        resampling=Resampling[settings["resampling"]],
        COORDINATE_OPERATION=settings["operation_proj"],
    )
    record = {
        "source_crs": settings["source_crs"],
        "target_crs": settings["target_crs"],
        "cell_grid_checked": True,
        "cell_count": len(cell_ids),
        "destination_transform": tuple(shifted)[:6],
        "operation": operation.description,
        "operation_epsg": settings["operation_epsg"],
        "operation_proj": settings["operation_proj"],
        "operation_accuracy_m": operation.accuracy,
        "proj_version": proj_version_str,
        "gdal_version": rasterio.__gdal_version__,
        "resampling": settings["resampling"],
        "offset_east_m": offset_east_m,
        "offset_north_m": offset_north_m,
    }
    return destination[rows, columns] * height_scale_to_m, record
