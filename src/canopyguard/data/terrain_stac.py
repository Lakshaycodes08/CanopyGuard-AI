"""Elevation from NASADEM on the Landsat grid, via the Planetary Computer."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def elevation_on_grid(
    grid: tuple[float, float, float, int, int],
    bbox_wgs84: tuple[float, float, float, float],
    stac_url: str,
    crs: str,
    config: dict[str, Any],
) -> NDArray[np.float32]:
    """Bilinear NASADEM elevation (m) on the grid; NaN where no tile covers."""
    import planetary_computer
    import pystac_client
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.vrt import WarpedVRT

    left, top, step, width, height = grid
    catalog = pystac_client.Client.open(
        stac_url, modifier=planetary_computer.sign_inplace
    )
    items = list(
        catalog.search(collections=[config["collection"]], bbox=bbox_wgs84).items()
    )
    if not items:
        raise RuntimeError("No NASADEM tile covers the study area")
    out = np.full((int(height), int(width)), np.nan, dtype=np.float32)
    transform = from_origin(left, top, step, step)
    for item in items:
        with (
            rasterio.open(item.assets[config["asset"]].href) as src,
            WarpedVRT(
                src,
                crs=crs,
                transform=transform,
                width=int(width),
                height=int(height),
                resampling=Resampling.bilinear,
                nodata=src.nodata,
            ) as vrt,
        ):
            block = vrt.read(1).astype(np.float32)
        if src.nodata is not None:
            block[block == src.nodata] = np.nan
        take = np.isnan(out) & np.isfinite(block)
        out[take] = block[take]
    return out
