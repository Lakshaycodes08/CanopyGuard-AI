from __future__ import annotations

import math

import numpy as np


def compute_segment_slope(
    elevation_start: float,
    elevation_end: float,
    length_m: float,
) -> float:
    """Compute longitudinal slope along corridor segment in degrees."""
    if length_m <= 0.0 or np.isnan(elevation_start) or np.isnan(elevation_end):
        return 0.0

    delta_z = abs(float(elevation_end) - float(elevation_start))
    slope_rad = math.atan(delta_z / float(length_m))
    return float(math.degrees(slope_rad))


def compute_aspect_components(aspect_deg: float) -> tuple[float, float]:
    """Compute continuous Northness and Eastness from aspect in degrees."""
    if np.isnan(aspect_deg):
        return 0.0, 0.0

    aspect_rad = math.radians(aspect_deg)
    northness = float(math.cos(aspect_rad))
    eastness = float(math.sin(aspect_rad))
    return northness, eastness
