"""ECHOSAT height drop on the Landsat grid, for cross-checking screens only."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

from canopyguard.data import echosat


def drop_mask(
    data: NDArray, band_years: list[int], source: dict[str, Any], inside: NDArray
) -> NDArray[np.float32]:
    """1 where height fell by at least the abrupt-change size between two years,
    0 where it did not, -1 where either year or the pixel is not usable."""
    first = band_years.index(int(source["from_year"]))
    last = band_years.index(int(source["to_year"]))
    nodata = source["nodata_value"]
    scale = source["height_scale_to_m"]
    before = data[first].astype(np.float32)
    after = data[last].astype(np.float32)
    usable = inside & (before != nodata) & (after != nodata)
    fall = (before - after) * scale
    mask = (fall >= float(source["abrupt_change_m"])).astype(np.float32)
    mask[~usable] = -1.0
    return mask


def drop_share_on_grid(
    source: dict[str, Any],
    bbox: tuple[float, float, float, float],
    grid: tuple[float, float, float, int, int],
) -> NDArray[np.float32]:
    """Share of 10 m pixels with a height drop inside each Landsat grid cell."""
    left, top, step, width, height = grid
    url = f"/vsicurl/{source['tile_url']}"
    with echosat.open_environment(source), rasterio.open(url) as src:
        echosat.validate_raster(src, source)
        box = echosat.read_box(src, bbox)
    mask = drop_mask(box.data, list(source["band_years"]), source, box.inside)
    out = np.full((int(height), int(width)), np.nan, dtype=np.float32)
    reproject(
        mask,
        out,
        src_transform=box.transform,
        src_crs=box.crs,
        src_nodata=-1.0,
        dst_transform=from_origin(left, top, step, step),
        dst_crs=box.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    return out


def compact_percent(share: NDArray[np.float32], factor: int) -> NDArray[np.uint8]:
    """Block means as whole percent (255 = no data), small enough to move by hand."""
    rows = share.shape[0] // factor * factor
    cols = share.shape[1] // factor * factor
    tiles = share[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(tiles, axis=(1, 3))
    return np.where(np.isnan(mean), 255, np.round(100 * mean)).astype(np.uint8)


def expand_percent(
    percent: NDArray[np.uint8], factor: int, shape: tuple[int, int]
) -> NDArray[np.float32]:
    """Repeat each percent over its block on a grid of `shape`; NaN outside."""
    share = np.where(percent == 255, np.nan, percent / 100.0).astype(np.float32)
    repeated = np.kron(share, np.ones((factor, factor), dtype=np.float32))
    out = np.full(shape, np.nan, dtype=np.float32)
    rows = min(shape[0], repeated.shape[0])
    cols = min(shape[1], repeated.shape[1])
    out[:rows, :cols] = repeated[:rows, :cols]
    return out
