"""TerraClimate 1981-2010 normals sampled onto the Landsat grid."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

# Variables that add over a year; the rest are averaged.
SUMMED = {"ppt", "def", "aet", "pet", "q"}


def climate_normals(
    bbox_wgs84: tuple[float, float, float, float],
    stac_url: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Annual normals on the TerraClimate grid around the study box."""
    import planetary_computer
    import pystac_client
    import xarray as xr

    catalog = pystac_client.Client.open(
        stac_url, modifier=planetary_computer.sign_inplace
    )
    asset = catalog.get_collection(config["collection"]).assets["zarr-abfs"]
    ds = xr.open_dataset(
        asset.href,
        **asset.extra_fields["xarray:open_kwargs"],
    )
    west, south, east, north = bbox_wgs84
    pad = float(config["margin_degrees"])
    ds = ds.sel(
        time=slice(config["normal_start"], config["normal_end"]),
        lon=slice(west - pad, east + pad),
        lat=slice(north + pad, south - pad),
    )
    years = ds.sizes["time"] / 12.0
    normals = {}
    for name in config["variables"]:
        total = ds[name].sum("time") if name in SUMMED else ds[name].mean("time")
        if name in SUMMED:
            total = total / years
        normals[name] = total.load().values.astype(np.float64)
    return {"lon": ds["lon"].values, "lat": ds["lat"].values, "normals": normals}


def sample_on_grid(
    climate: dict[str, Any],
    grid: tuple[float, float, float, int, int],
    crs: str,
) -> dict[str, NDArray[np.float32]]:
    """Bilinear sample of each normal at the grid pixel centres."""
    from pyproj import Transformer
    from scipy.interpolate import RegularGridInterpolator

    left, top, step, width, height = grid
    x = left + (np.arange(int(width)) + 0.5) * step
    y = top - (np.arange(int(height)) + 0.5) * step
    xx, yy = np.meshgrid(x, y)
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(xx, yy)
    lat_axis = climate["lat"]
    order = np.argsort(lat_axis)
    points = np.stack([lat.ravel(), lon.ravel()], axis=1)
    out = {}
    for name, values in climate["normals"].items():
        interpolator = RegularGridInterpolator(
            (lat_axis[order], climate["lon"]),
            values[order],
            bounds_error=False,
            fill_value=np.nan,
        )
        out[f"clim_{name}"] = interpolator(points).reshape(lon.shape).astype(np.float32)
    return out
