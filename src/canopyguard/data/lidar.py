from __future__ import annotations

import numpy as np


def compute_height_above_ground(
    z_points: np.ndarray,
    dem_elevation: np.ndarray | float,
) -> np.ndarray:
    """Normalize raw LiDAR return elevations to Height Above Ground (HAG)."""
    hag = z_points.astype(np.float64) - np.asarray(dem_elevation, dtype=np.float64)
    return np.maximum(0.0, hag)


def aggregate_canopy_percentile(
    hag_points: np.ndarray,
    percentile: float = 95.0,
    min_points: int = 5,
) -> float:
    """Calculate the target percentile canopy height for ground-truth validation."""
    if len(hag_points) < min_points:
        return 0.0
    return float(np.percentile(hag_points, percentile))
