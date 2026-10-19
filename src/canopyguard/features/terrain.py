"""Slope, aspect and local position from an elevation grid."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter


def terrain_features(
    elevation: NDArray[np.float32], step_m: float, tpi_radius_pixels: int
) -> dict[str, NDArray[np.float32]]:
    """Elevation, slope in degrees, northness, eastness and TPI.

    Rows run south, so the downhill-facing north component is d(z)/d(row).
    Flat cells get zero northness and eastness.
    """
    d_row, d_col = np.gradient(elevation, step_m)
    magnitude = np.hypot(d_row, d_col)
    slope = np.degrees(np.arctan(magnitude))
    with np.errstate(divide="ignore", invalid="ignore"):
        northness = np.where(magnitude > 0, d_row / magnitude, 0.0)
        eastness = np.where(magnitude > 0, -d_col / magnitude, 0.0)
    size = 2 * tpi_radius_pixels + 1
    filled = np.where(np.isfinite(elevation), elevation, np.nanmean(elevation))
    tpi = elevation - uniform_filter(filled, size=size, mode="nearest")
    nan = ~np.isfinite(elevation)
    features = {
        "elevation_m": elevation,
        "slope_deg": slope,
        "northness": northness,
        "eastness": eastness,
        "tpi": tpi,
    }
    return {
        name: np.where(nan, np.nan, values).astype(np.float32)
        for name, values in features.items()
    }
