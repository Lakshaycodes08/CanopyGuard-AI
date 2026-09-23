"""PDAL pipeline construction for matched canopy height models.

PDAL is imported inside `run_pipeline` only. Every other function here returns
plain data and is testable without PDAL installed.

The same pipeline runs for every epoch. Differing ground algorithms, height
thresholds, raster reducers or raster grids between epochs would appear as
canopy change.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from canopyguard.lidar.ept import pdal_bounds
from canopyguard.lidar.grid import grid_box


FLAG_EXPRESSION = "Synthetic == 0 && Withheld == 0 && Overlap == 0"


def reader_stage(input_path: str) -> dict[str, Any]:
    """Read a point cloud file."""
    return {"type": "readers.las", "filename": str(input_path)}


def return_guard_stage() -> dict[str, Any]:
    """Drop returns whose return numbering is unset.

    A return carrying zero for ReturnNumber or NumberOfReturns is invalid. The
    ground classifier rejects a tile outright when it meets a mixture of valid
    and invalid numbering, so these returns are removed before anything reads
    them.
    """
    return {
        "type": "filters.expression",
        "expression": "ReturnNumber > 0 && NumberOfReturns > 0",
    }


def flag_filter_stage() -> dict[str, Any]:
    """Drop withheld, overlap and synthetic returns.

    Withheld and overlap are flags, not classification values, so a filter on
    Classification does not reach them. The EPT and LAS readers expose the
    flags as the separate dimensions Synthetic, KeyPoint, Withheld and Overlap;
    key point returns are kept.

    Overlap returns are the edge-of-swath returns of an adjacent strip. Two
    acquisitions do not overlap in the same places, so leaving them in puts a
    strip-geometry difference straight into the measured change.
    """
    return {
        "type": "filters.expression",
        "expression": FLAG_EXPRESSION,
    }


def stats_stage(dimensions: list[str]) -> dict[str, Any]:
    """Record per-dimension statistics at this point in the pipeline."""
    if not dimensions:
        raise ValueError("At least one dimension is required")
    return {"type": "filters.stats", "dimensions": ",".join(dimensions)}


def reprojection_stage(target_crs: str) -> dict[str, Any]:
    """Reproject to the common working frame."""
    return {"type": "filters.reprojection", "out_srs": target_crs}


def class_filter_stage(drop_classes: list[int]) -> dict[str, Any]:
    """Drop noise, water and overlap classes."""
    if not drop_classes:
        raise ValueError("At least one class must be dropped")
    terms = " && ".join(
        f"Classification != {int(value)}" for value in sorted(set(drop_classes))
    )
    return {"type": "filters.expression", "expression": terms}


def scan_angle_stage(max_abs_deg: float) -> dict[str, Any]:
    """Keep returns inside the scan-angle band shared by both acquisitions."""
    if max_abs_deg <= 0:
        raise ValueError("Scan angle limit must be positive")
    return {
        "type": "filters.expression",
        "expression": (
            f"ScanAngleRank >= {-float(max_abs_deg)} "
            f"&& ScanAngleRank <= {float(max_abs_deg)}"
        ),
    }


def crop_stage(box: tuple[float, float, float, float]) -> dict[str, Any]:
    """Clip to the exact tile extent in the working frame.

    The read window is a rectangle in the frame the resource is indexed in,
    which is not a rectangle in the working frame, so the surplus is removed
    after reprojection and before anything is rasterised.
    """
    return {"type": "filters.crop", "bounds": pdal_bounds(box)}


def decimation_stage(radius_m: float) -> dict[str, Any]:
    """Thin to a common point density with Poisson-disk sampling.

    Thinning precedes ground classification so that both epochs are classified
    at the same density. Classifying at native density and thinning afterwards
    would leave a density-dependent difference in the ground surface, which is
    the one error that does not cancel when two epochs are subtracted.
    """
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


def ground_only_stage() -> dict[str, Any]:
    """Keep the returns the ground classifier accepted."""
    return {"type": "filters.expression", "expression": "Classification == 2"}


def hag_stage(method: str) -> dict[str, Any]:
    """Normalise return elevations to height above ground."""
    allowed = {"hag_delaunay", "hag_nn"}
    if method not in allowed:
        raise ValueError(f"Height above ground method must be one of {sorted(allowed)}")
    return {"type": f"filters.{method}"}


def raster_stage(
    output_path: str,
    output_type: str,
    grid: dict[str, Any],
    dimension: str | None = None,
    binmode: bool = False,
) -> dict[str, Any]:
    """Write a raster onto a fixed grid with a single reducer.

    Origin and size come from the grid rather than from the extent of the
    points that arrive, so every epoch of a tile lands on identical cells and
    the two rasters subtract without resampling.

    With binmode a point contributes only to the cell it falls in. Without it
    the reducer gathers points within a search radius, which turns a canopy
    apex into a plateau and makes the result depend on point density.
    """
    for key in ("origin_x", "origin_y", "width", "height", "resolution_m"):
        if key not in grid:
            raise ValueError(f"Grid is missing {key}")
    if int(grid["width"]) < 1 or int(grid["height"]) < 1:
        raise ValueError("Grid must have at least one cell on each side")

    stage: dict[str, Any] = {
        "type": "writers.gdal",
        "filename": str(output_path),
        "output_type": output_type,
        "resolution": float(grid["resolution_m"]),
        "origin_x": float(grid["origin_x"]),
        "origin_y": float(grid["origin_y"]),
        "width": int(grid["width"]),
        "height": int(grid["height"]),
        "gdaldriver": "GTiff",
        "allow_empty": True,
        "binmode": bool(binmode),
    }
    if dimension:
        stage["dimension"] = dimension
    return stage


def height_threshold_stage(minimum_m: float) -> dict[str, Any]:
    """Keep returns above a pit-free layer threshold."""
    if minimum_m < 0:
        raise ValueError("Layer threshold must be non-negative")
    return {
        "type": "filters.expression",
        "expression": f"HeightAboveGround >= {float(minimum_m)}",
    }


def _preamble(
    reader: dict[str, Any], grid: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    harmonization = config["harmonization"]
    stages = [dict(reader), return_guard_stage()]
    if harmonization.get("drop_class_flags", True):
        stages.append(flag_filter_stage())
    stages += [
        reprojection_stage(harmonization["target_crs"]),
        class_filter_stage(harmonization["drop_classes"]),
        scan_angle_stage(harmonization["max_scan_angle_deg"]),
        crop_stage(grid_box(grid)),
        decimation_stage(harmonization["sample_radius_m"]),
        stats_stage(harmonization["stats_dimensions"]),
        ground_stage(config["chm"]["smrf"]),
    ]
    return stages


def build_terrain_pipeline(
    reader: dict[str, Any],
    dtm_path: str,
    dsm_path: str,
    grid: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Pipeline producing the ground surface and the top-of-return surface."""
    chm = config["chm"]
    stages = _preamble(reader, grid, config)
    stages.append(
        raster_stage(
            dsm_path, chm["dsm_output_type"], grid, binmode=bool(chm["dsm_binmode"])
        )
    )
    stages.append(ground_only_stage())
    stages.append(
        raster_stage(
            dtm_path, chm["dtm_output_type"], grid, binmode=bool(chm["dtm_binmode"])
        )
    )
    return {"pipeline": stages}


def build_layer_pipeline(
    reader: dict[str, Any],
    layer_path: str,
    threshold_m: float,
    grid: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Pipeline producing one pit-free canopy layer."""
    chm = config["chm"]
    stages = _preamble(reader, grid, config)
    stages.append(hag_stage(chm["height_above_ground"]))
    stages.append(height_threshold_stage(threshold_m))
    stages.append(
        raster_stage(
            layer_path,
            "max",
            grid,
            dimension="HeightAboveGround",
            binmode=bool(chm["dsm_binmode"]),
        )
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


def run_pipeline(pipeline: dict[str, Any]) -> dict[str, Any]:
    """Execute a PDAL pipeline and return its point count and statistics.

    The count is the number of points leaving the last stage. The terrain
    pipeline ends on the ground surface, so that count is ground returns, and
    the count of everything retained is taken from the statistics stage
    instead.

    This is the only function in the package that requires PDAL.
    """
    import json

    import pdal

    executed = pdal.Pipeline(json.dumps(pipeline))
    points = int(executed.execute())
    metadata = executed.metadata
    if not isinstance(metadata, dict):
        metadata = json.loads(metadata)
    return {"points": points, "stats": pipeline_stats(metadata)}


def pipeline_stats(metadata: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Per-dimension statistics recorded by the statistics stage."""
    node = metadata.get("metadata", metadata).get("filters.stats", {})
    if isinstance(node, list):
        node = node[0] if node else {}
    return {
        entry["name"]: {
            key: float(entry[key])
            for key in ("count", "minimum", "maximum", "average")
            if key in entry
        }
        for entry in node.get("statistic", [])
        if "name" in entry
    }
