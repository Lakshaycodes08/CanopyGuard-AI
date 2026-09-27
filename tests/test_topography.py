from __future__ import annotations

import numpy as np

from canopyguard.data.topography import compute_aspect_components, compute_segment_slope


def test_compute_segment_slope() -> None:
    assert np.isclose(compute_segment_slope(100.0, 100.0, 100.0), 0.0)
    assert np.isclose(compute_segment_slope(0.0, 100.0, 100.0), 45.0)


def test_compute_aspect_components() -> None:
    northness, eastness = compute_aspect_components(0.0)
    assert np.isclose(northness, 1.0)
    assert np.isclose(eastness, 0.0)

    northness, eastness = compute_aspect_components(90.0)
    assert np.isclose(northness, 0.0)
    assert np.isclose(eastness, 1.0)
