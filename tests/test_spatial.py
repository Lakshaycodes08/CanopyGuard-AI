from __future__ import annotations

import math

from canopyguard.data.spatial import haversine_distance_m


def test_haversine_distance_m() -> None:
    # 1 degree of latitude is roughly 111km
    dist = haversine_distance_m(-122.0, 38.0, -122.0, 39.0)
    assert math.isclose(dist, 111195.0, rel_tol=0.01)
