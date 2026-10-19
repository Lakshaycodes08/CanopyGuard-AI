"""Per-pixel optical history features from yearly Landsat summer composites.

Every input composite is dated before the forecast cutoff, so the features
describe the past only. Missing years stay NaN and are skipped, not filled.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

BAND_ORDER = ["blue", "green", "red", "nir", "swir1", "swir2"]


def normalized_difference(
    left: NDArray[np.float32], right: NDArray[np.float32]
) -> NDArray[np.float32]:
    """(left - right) / (left + right) with zero denominators set to NaN."""
    total = left + right
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (left - right) / total
    ratio[total == 0] = np.nan
    return ratio.astype(np.float32)


def yearly_indices(composites: NDArray[np.float32]) -> dict[str, NDArray[np.float32]]:
    """NDVI, NBR and NDMI per year; composites are (year, band, row, column)."""
    band = {name: composites[:, i] for i, name in enumerate(BAND_ORDER)}
    return {
        "ndvi": normalized_difference(band["nir"], band["red"]),
        "nbr": normalized_difference(band["nir"], band["swir2"]),
        "ndmi": normalized_difference(band["nir"], band["swir1"]),
    }


def trend_per_year(series: NDArray[np.float32], years: NDArray) -> NDArray[np.float32]:
    """Least-squares slope per year over the finite values of each pixel."""
    t = np.asarray(years, dtype=np.float32)[:, None, None]
    ok = np.isfinite(series)
    n = ok.sum(axis=0)
    y = np.where(ok, series, 0.0)
    t_ok = np.where(ok, t, 0.0)
    t_mean = t_ok.sum(axis=0) / np.maximum(n, 1)
    y_mean = y.sum(axis=0) / np.maximum(n, 1)
    dt = np.where(ok, t - t_mean, 0.0)
    denominator = (dt**2).sum(axis=0)
    numerator = (dt * np.where(ok, series - y_mean, 0.0)).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = numerator / denominator
    slope[(n < 4) | (denominator == 0)] = np.nan
    return slope.astype(np.float32)


def history_features(
    composites: NDArray[np.float32], years: NDArray, config: dict[str, Any]
) -> dict[str, NDArray[np.float32]]:
    """Feature rasters (row, column) from yearly composites up to the cutoff."""
    recent = slice(-int(config["recent_years"]), None)
    indices = yearly_indices(composites)
    features: dict[str, NDArray[np.float32]] = {}
    for name, series in indices.items():
        features[f"{name}_recent"] = np.nanmean(series[recent], axis=0)
        features[f"{name}_mean"] = np.nanmean(series, axis=0)
        features[f"{name}_trend"] = trend_per_year(series, years)
    ndvi = indices["ndvi"]
    features["ndvi_range"] = np.nanmax(ndvi, axis=0) - np.nanmin(ndvi, axis=0)
    for i, name in enumerate(BAND_ORDER):
        features[f"{name}_recent"] = np.nanmean(composites[recent, i], axis=0)
    return {key: value.astype(np.float32) for key, value in features.items()}
