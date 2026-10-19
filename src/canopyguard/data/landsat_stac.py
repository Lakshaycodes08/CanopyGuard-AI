"""Landsat Collection 2 Level-2 summer composites from the Planetary Computer.

Scenes are read straight from the cloud-optimised GeoTIFFs onto the native
30 m UTM grid, so no resampling touches the reflectance. Every scene must be
dated before the forecast cutoff; the builder raises otherwise.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

BAND_NAMES = ["blue", "green", "red", "nir", "swir1", "swir2"]


def season_window(year: int, config: dict[str, Any]) -> tuple[date, date]:
    """Summer window for a year, clipped so it never reaches the cutoff."""
    cutoff = date.fromisoformat(config["cutoff"])
    start = date.fromisoformat(f"{year}-{config['season_start']}")
    end = date.fromisoformat(f"{year}-{config['season_end']}")
    if year > cutoff.year or start >= cutoff:
        msg = f"Season {year} starts on or after the cutoff {cutoff}"
        raise ValueError(msg)
    return start, min(end, cutoff - timedelta(days=1))


def assert_before_cutoff(scene_dates: list[date], cutoff: date) -> None:
    """Raise if any scene was acquired on or after the cutoff."""
    late = [d for d in scene_dates if d >= cutoff]
    if late:
        msg = f"{len(late)} scene(s) dated on or after the cutoff {cutoff}: {late[:3]}"
        raise ValueError(msg)


def study_grid(bbox_utm: tuple[float, float, float, float], config: dict[str, Any]):
    """Snap a UTM box outward to the Landsat grid; return left, top, width, height."""
    step = float(config["grid_resolution_m"])
    offset = float(config["grid_origin_offset_m"])
    west, south, east, north = bbox_utm
    left = np.floor((west - offset) / step) * step + offset
    right = np.ceil((east - offset) / step) * step + offset
    bottom = np.floor((south - offset) / step) * step + offset
    top = np.ceil((north - offset) / step) * step + offset
    width = int(round((right - left) / step))
    height = int(round((top - bottom) / step))
    return float(left), float(top), width, height


def mask_and_scale(
    raw: NDArray[np.uint16], qa: NDArray[np.uint16], config: dict[str, Any]
) -> NDArray[np.float32]:
    """Surface reflectance with cloud, shadow, snow and fill set to NaN."""
    bad = (qa & int(config["qa_reject_mask"])) != 0
    bad = bad | (raw == 0).any(axis=0)
    scaled = raw.astype(np.float32) * config["reflectance_scale"]
    scaled += config["reflectance_offset"]
    scaled[:, bad] = np.nan
    return scaled


def read_scene(item: Any, grid: tuple, config: dict[str, Any]) -> NDArray[np.float32]:
    """Read one scene's six bands onto the study grid as masked reflectance."""
    import rasterio
    from rasterio.windows import Window

    left, top, width, height = grid
    step = float(config["grid_resolution_m"])
    bands = [item.assets[config["band_assets"][name]].href for name in BAND_NAMES]
    qa_href = item.assets[config["qa_asset"]].href

    def read(href: str, fill: int) -> NDArray[np.uint16]:
        with rasterio.open(href) as src:
            col = int(round((left - src.transform.c) / step))
            row = int(round((src.transform.f - top) / step))
            window = Window(col, row, width, height)
            return src.read(1, window=window, boundless=True, fill_value=fill)

    raw = np.stack([read(href, 0) for href in bands])
    return mask_and_scale(raw, read(qa_href, 1), config)


def read_scene_retrying(item: Any, grid: tuple, config: dict[str, Any]):
    """Read a scene, retrying transient network errors."""
    last: Exception | None = None
    for _ in range(int(config["request_retries"])):
        try:
            return read_scene(item, grid, config)
        except Exception as error:  # noqa: BLE001 - network errors vary by backend
            last = error
    raise RuntimeError(f"Scene {item.id} failed: {last}") from last


def year_composite(
    items: list[Any], grid: tuple, config: dict[str, Any]
) -> tuple[NDArray[np.float32], NDArray[np.int16]]:
    """Median reflectance and clear-observation count for one summer."""
    left, top, width, height = grid
    if not items:
        empty = np.full((len(BAND_NAMES), height, width), np.nan, np.float32)
        return empty, np.zeros((height, width), np.int16)
    with ThreadPoolExecutor(max_workers=int(config["workers"])) as pool:
        scenes = list(pool.map(lambda it: read_scene_retrying(it, grid, config), items))
    stack = np.stack(scenes)
    clear = np.isfinite(stack[:, 0]).sum(axis=0).astype(np.int16)
    return np.nanmedian(stack, axis=0).astype(np.float32), clear
