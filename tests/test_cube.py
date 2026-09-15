import numpy as np
import pytest

from canopyguard.features.cube import (
    estimate_array_gib,
    monthly_clear_composite,
    scale_reflectance,
)


def test_scale_reflectance_uses_metadata_offset() -> None:
    digital_number = np.array([0, 1000, 2000], dtype=np.uint16)

    result = scale_reflectance(digital_number, 10000, -1000, nodata_value=0)

    np.testing.assert_allclose(result, [np.nan, 0.0, 0.1])


def test_scale_reflectance_preserves_valid_negative_values() -> None:
    result = scale_reflectance([1], 10000, -1000, nodata_value=0)

    np.testing.assert_allclose(result, [-0.0999])


def test_scale_reflectance_rejects_invalid_quantification() -> None:
    with pytest.raises(ValueError, match="positive"):
        scale_reflectance([1, 2], 0)


def test_monthly_clear_composite_masks_and_counts() -> None:
    reflectance = np.array(
        [
            [[[1, 2], [3, 4]]],
            [[[5, 6], [7, 8]]],
            [[[9, 10], [11, 12]]],
        ],
        dtype=np.float32,
    )
    scl = np.array(
        [
            [[4, 9], [4, 4]],
            [[4, 4], [3, 4]],
            [[4, 9], [3, 4]],
        ]
    )

    composite, clear_count = monthly_clear_composite(reflectance, scl, [3, 9])

    np.testing.assert_allclose(composite, [[[5, 6], [3, 8]]])
    np.testing.assert_array_equal(clear_count, [[3, 1], [1, 3]])


def test_monthly_clear_composite_rejects_misaligned_grids() -> None:
    with pytest.raises(ValueError, match="align"):
        monthly_clear_composite(np.ones((2, 1, 2, 2)), np.ones((1, 2, 2)), [9])


def test_estimate_array_gib_accounts_for_working_copies() -> None:
    one_copy = estimate_array_gib((1024, 1024), "float32")

    assert one_copy == pytest.approx(1 / 256)
    assert estimate_array_gib((1024, 1024), "float32", 3) == pytest.approx(3 / 256)
