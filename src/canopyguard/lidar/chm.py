"""PDAL pipeline construction for matched canopy height models.

PDAL is imported inside `run_pipeline` only. Every other function here returns
plain data and is testable without PDAL installed.

The same pipeline runs for every epoch. Differing ground algorithms, height
thresholds or raster reducers between epochs would appear as canopy change.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


def reader_stage(input_path: str) -> dict[str, Any]:
    """Read a point cloud file."""
    return {"type": "readers.las", "filename": str(input_path)}


def reprojection_stage(target_crs: str) -> dict[str, Any]:
    """Reproject to the common working frame."""
    return {"type": "filters.reprojection", "out_srs": target_crs}


def class_filter_stage(drop_classes: list[int]) -> dict[str, Any]:
    """Drop noise, water and overlap classes.

    Each excluded class needs its own negated range. A single range holding a
    comma-separated list is not valid range syntax.
    """
    if not drop_classes:
        raise ValueError("At least one class must be dropped")
    ranges = ",".join(
        f"Classification![{int(value)}:{int(value)}]" for value in drop_classes
    )
    return {"type": "filters.range", "limits": ranges}


def scan_angle_stage(max_abs_deg: float) -> dict[str, Any]:
    """Keep returns inside the scan-angle band shared by both acquisitions."""
    if max_abs_deg <= 0:
        raise ValueError("Scan angle limit must be positive")
    return {
        "type": "filters.range",
        "limits": f"ScanAngleRank[{-max_abs_deg}:{max_abs_deg}]",
    }


def decimation_stage(radius_m: float) -> dict[str, Any]:
    """Thin to a common point density with Poisson-disk sampling."""
    if radius_m <= 0:
        raise ValueError("Sampling radius must be positive")
    return {"type": "filters.sample", "radius": float(radius_m)}


def ground_stage(smrf: dict[str, Any]) -> dict[str, Any]:
    """Classify ground with fixed parameters shared by every epoch."""
    required = ("scalar", "slope", "threshold", "window")
    missing = [key for key in required if key not in smrf]
    if missing:
        raise ValueError("Missing SMRF parameters: " + ", ".join(missing))
    return {"type": "filters.smrf", **{key: smrf[key] for key in required}}


def hag_stage(method: str) -> dict[str, Any]:
    """Normalise return elevations to height above ground."""
    allowed = {"hag_delaunay", "hag_nn"}
    if method not in allowed:
        raise ValueError(f"Height above ground method must be one of {sorted(allowed)}")
    return {"type": f"filters.{method}"}


def raster_stage(
    output_path: str, output_type: str, resolution: float, dimension: str | None = None
) -> dict[str, Any]:
    """Write a raster with a single reducer."""
    if resolution <= 0:
        raise ValueError("Raster resolution must be positive")
    stage: dict[str, Any] = {
        "type": "writers.gdal",
        "filename": str(output_path),
        "output_type": output_type,
        "resolution": float(resolution),
        "gdaldriver": "GTiff",
    }
    if dimension:
        stage["dimension"] = dimension
    return stage


def height_threshold_stage(minimum_m: float) -> dict[str, Any]:
    """Keep returns above a pit-free layer threshold."""
    if minimum_m < 0:
        raise ValueError("Layer threshold must be non-negative")
    return {"type": "filters.range", "limits": f"HeightAboveGround[{minimum_m}:]"}


def _preamble(reader: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    harmonization = config["harmonization"]
    return [
        dict(reader),
        reprojection_stage(harmonization["target_crs"]),
        class_filter_stage(harmonization["drop_classes"]),
        scan_angle_stage(harmonization["max_scan_angle_deg"]),
        decimation_stage(harmonization["sample_radius_m"]),
    ]


def build_terrain_pipeline(
    reader: dict[str, Any], dtm_path: str, dsm_path: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Pipeline producing the ground surface and the top-of-return surface."""
    chm = config["chm"]
    stages = _preamble(reader, config)
    stages.append(ground_stage(chm["smrf"]))
    stages.append(raster_stage(dsm_path, chm["dsm_output_type"], chm["resolution_m"]))
    stages.append({"type": "filters.range", "limits": "Classification[2:2]"})
    stages.append(raster_stage(dtm_path, chm["dtm_output_type"], chm["resolution_m"]))
    return {"pipeline": stages}


def build_layer_pipeline(
    reader: dict[str, Any], layer_path: str, threshold_m: float, config: dict[str, Any]
) -> dict[str, Any]:
    """Pipeline producing one pit-free canopy layer."""
    chm = config["chm"]
    stages = _preamble(reader, config)
    stages.append(ground_stage(chm["smrf"]))
    stages.append(hag_stage(chm["height_above_ground"]))
    stages.append(height_threshold_stage(threshold_m))
    stages.append(
        raster_stage(layer_path, "max", chm["resolution_m"], "HeightAboveGround")
    )
    return {"pipeline": stages}


def pit_free_combine(
    layers: list[ArrayLike], clamp_min_m: float, clamp_max_m: float
) -> NDArray[np.float64]:
    """Combine pit-free layers by taking the maximum at each cell."""
    if not layers:
        raise ValueError("At least one layer is required")
    if clamp_min_m >= clamp_max_m:
        raise ValueError("Require clamp_min_m < clamp_max_m")

    stack = np.stack([np.asarray(layer, dtype=np.float64) for layer in layers])
    with np.errstate(invalid="ignore"):
        combined = np.nanmax(stack, axis=0)
    outside = (combined < clamp_min_m) | (combined > clamp_max_m)
    return np.where(outside, np.nan, combined)


def run_pipeline(pipeline: dict[str, Any]) -> int:
    """Execute a PDAL pipeline and return the point count.

    This is the only function in the package that requires PDAL.
    """
    import json

    import pdal

    executed = pdal.Pipeline(json.dumps(pipeline))
    return int(executed.execute())
