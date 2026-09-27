"""Raster reading and writing for the LiDAR truth pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


def read_grid(path: str | Path) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Read a single-band raster as float with no-data as not-a-number."""
    import rasterio

    with rasterio.open(str(path)) as source:
        profile = dict(source.profile)
        band = source.read(1, masked=True).filled(np.nan).astype(np.float64)
    return band, profile


def write_grid(
    path: str | Path, array: NDArray[np.float64], profile: dict[str, Any]
) -> Path:
    """Write a single-band float raster, preserving the source geotransform."""
    import rasterio

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    updated = {**profile, "dtype": "float32", "count": 1, "nodata": np.nan}
    with rasterio.open(str(output), "w", **updated) as destination:
        destination.write(array.astype(np.float32), 1)
    return output


def scaled_profile(profile: dict[str, Any], factor: int) -> dict[str, Any]:
    """Profile for a grid aggregated by an integer block factor."""
    if factor < 1:
        raise ValueError("Aggregation factor must be at least one")
    transform = profile["transform"]
    return {
        **profile,
        "width": profile["width"] // factor,
        "height": profile["height"] // factor,
        "transform": transform * transform.scale(factor, factor),
    }
