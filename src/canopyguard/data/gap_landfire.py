"""USGS GAP / LANDFIRE 2011 ecological systems onto the Landsat grid."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import numpy as np
from numpy.typing import NDArray


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def ecosystem_rasters(
    grid: tuple[float, float, float, int, int],
    bbox_wgs84: tuple[float, float, float, float],
    stac_url: str,
    crs: str,
    config: dict[str, Any],
) -> dict[str, NDArray[np.float32]]:
    """0/1 rasters per ecological system with enough pixels; NaN where unmapped."""
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
        raise RuntimeError("No GAP tile covers the study area")
    limit = date.fromisoformat(config["max_item_date"])
    late = [i.id for i in items if i.datetime.date() > limit]
    if late:
        msg = f"GAP item(s) dated after {limit}: {late}"
        raise ValueError(msg)

    names = items[0].properties["label:classes"][0]["classes"]
    codes = np.zeros((int(height), int(width)), dtype=np.int32)
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
                resampling=Resampling.nearest,
                nodata=0,
            ) as vrt,
        ):
            block = vrt.read(1).astype(np.int32)
        codes = np.where(codes == 0, block, codes)

    unmapped = codes == 0
    out: dict[str, NDArray[np.float32]] = {}
    for value in np.unique(codes[~unmapped]):
        hits = codes == value
        if hits.sum() < int(config["min_pixels_per_class"]):
            continue
        layer = hits.astype(np.float32)
        layer[unmapped] = np.nan
        out[f"eco_{slug(names[int(value)])}"] = layer
    return out
