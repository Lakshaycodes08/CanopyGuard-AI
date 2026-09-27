from __future__ import annotations

import numpy as np
import pytest

from canopyguard.features.landsat import (
    FILL,
    block_grid,
    clear,
    normalised_difference,
    pixel_grid_request,
    reflectance,
    structured_to_stack,
    with_indices,
)

TRANSFORM = (1.0, 0.0, 500000.0, 0.0, -1.0, 4270000.0)


def test_block_grid_keeps_whole_blocks_from_the_upper_left_corner():
    grid = block_grid(TRANSFORM, 505, 481, 30)
    assert (grid["width"], grid["height"]) == (16, 16)
    assert (grid["scale_x"], grid["scale_y"]) == (30.0, -30.0)
    assert (grid["left"], grid["top"]) == (500000.0, 4270000.0)


def test_block_grid_rejects_rotation_and_oversized_blocks():
    with pytest.raises(ValueError, match="north up"):
        block_grid((1.0, 0.5, 0.0, 0.0, -1.0, 0.0), 10, 10, 2)
    with pytest.raises(ValueError, match="exceeds"):
        block_grid(TRANSFORM, 20, 20, 30)


def test_pixel_grid_request_carries_the_affine_grid():
    request = pixel_grid_request(block_grid(TRANSFORM, 60, 60, 30), "EPSG:6339")
    assert request["dimensions"] == {"width": 2, "height": 2}
    assert request["affineTransform"]["scaleY"] == -30.0
    assert request["affineTransform"]["translateY"] == 4270000.0
    assert request["crsCode"] == "EPSG:6339"


def test_reflectance_applies_collection_two_scaling():
    assert reflectance([7273, 43636])[0] == pytest.approx(0.0, abs=1e-4)
    assert reflectance([7273, 43636])[1] == pytest.approx(1.0, abs=1e-4)


def test_clear_rejects_fill_cloud_shadow_and_snow():
    qa = np.array([21824, 1, 8, 16, 32, 2, 4])
    assert clear(qa).tolist() == [True, False, False, False, False, False, False]


def test_indices_follow_their_definitions():
    stack = {
        band: np.array([0.1])
        for band in ["blue", "green", "red", "nir", "swir1", "swir2"]
    }
    stack["nir"] = np.array([0.5])
    out = with_indices(stack)
    assert out["ndvi"][0] == pytest.approx(0.4 / 0.6)
    assert np.isnan(normalised_difference([0.0], [0.0])[0])
    with pytest.raises(ValueError, match="Missing bands"):
        with_indices({"nir": np.array([1.0])})


def test_structured_array_fill_becomes_missing():
    array = np.zeros((1, 2), dtype=[("nir", "f8"), ("clear_count", "f8")])
    array["nir"] = [[0.3, FILL]]
    array["clear_count"] = [[4.0, FILL]]
    stack = structured_to_stack(array)
    assert stack["nir"][0, 0] == 0.3 and np.isnan(stack["nir"][0, 1])
    assert stack["clear_count"].tolist() == [[4.0, 0.0]]
