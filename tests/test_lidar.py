from __future__ import annotations

import numpy as np

from canopyguard.data.lidar import (
    aggregate_canopy_percentile,
    compute_height_above_ground,
)


def test_compute_height_above_ground() -> None:
    z_points = np.array([105.0, 98.0, 110.0])
    dem = 100.0
    hag = compute_height_above_ground(z_points, dem)
    assert np.allclose(hag, [5.0, 0.0, 10.0])


def test_aggregate_canopy_percentile() -> None:
    hag_points = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    p95 = aggregate_canopy_percentile(hag_points, percentile=95.0, min_points=3)
    assert p95 > 4.5

    # Not enough points
    p95_empty = aggregate_canopy_percentile(hag_points, percentile=95.0, min_points=10)
    assert p95_empty == 0.0
