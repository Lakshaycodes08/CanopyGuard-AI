"""Small, source-independent operations for the monthly raster cube."""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


def scale_reflectance(
    digital_number: ArrayLike,
    quantification_value: float,
    additive_offset: ArrayLike = 0.0,
    nodata_value: float | None = None,
) -> NDArray[np.float32]:
    """Apply metadata scaling, mask no-data, and keep valid negative values."""
    if quantification_value <= 0:
        raise ValueError("Quantification value must be positive")

    values = np.asarray(digital_number, dtype=np.float32)
    offsets = np.asarray(additive_offset, dtype=np.float32)
    try:
        reflectance = (values + offsets) / quantification_value
    except ValueError as error:
        raise ValueError("Additive offset is not broadcastable to the data") from error
    if nodata_value is not None:
        reflectance = np.where(values == nodata_value, np.nan, reflectance)
    return reflectance.astype(np.float32, copy=False)


def monthly_clear_composite(
    reflectance: ArrayLike,
    scene_classification: ArrayLike,
    excluded_classes: Sequence[int],
) -> tuple[NDArray[np.float32], NDArray[np.uint16]]:
    """Return a clear-pixel median and observation count for one month."""
    values = np.asarray(reflectance, dtype=np.float32)
    classes = np.asarray(scene_classification)
    if values.ndim != 4 or classes.ndim != 3:
        raise ValueError(
            "Expected reflectance [observation, band, y, x] and SCL [observation, y, x]"
        )
    if values.shape[0] != classes.shape[0] or values.shape[2:] != classes.shape[1:]:
        raise ValueError("Reflectance and SCL grids must align")

    invalid = np.isin(classes, excluded_classes)
    masked = np.where(invalid[:, np.newaxis, :, :], np.nan, values)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        composite = np.nanmedian(masked, axis=0)
    clear_count = np.count_nonzero(~invalid, axis=0)
    if clear_count.max(initial=0) > np.iinfo(np.uint16).max:
        raise ValueError("Clear-observation count exceeds uint16 capacity")
    return composite.astype(np.float32), clear_count.astype(np.uint16)


def estimate_array_gib(
    shape: Sequence[int], dtype: str, working_copies: int = 1
) -> float:
    """Estimate uncompressed array storage in gibibytes."""
    if not shape or any(dimension <= 0 for dimension in shape):
        raise ValueError("Array dimensions must be positive")
    if working_copies <= 0:
        raise ValueError("Working copies must be positive")

    byte_count = math.prod(shape) * np.dtype(dtype).itemsize * working_copies
    return byte_count / 1024**3
