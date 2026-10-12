"""Check ECHOSAT annual height coverage over the configured study box.

ECHOSAT maps are modeled height estimates, not measurements. This module counts
usable pixels only. It makes no claim that year-to-year differences are a
validated growth signal; that needs a check against repeat airborne LiDAR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple
from urllib.request import Request, urlopen

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from canopyguard.config import require_keys
from canopyguard.io import ensure_parent
from canopyguard.provenance import Box

WGS84 = "EPSG:4326"
REQUIRED_KEYS = [
    "tile_url",
    "band_years",
    "check_years",
    "nodata_value",
    "height_scale_to_m",
    "abrupt_change_m",
    "request_timeout_seconds",
    "http_max_retry",
]


class BoxRead(NamedTuple):
    """Bands read over the study box plus the geometry needed to interpret them."""

    data: np.ndarray
    window: Window
    transform: Affine
    inside: np.ndarray
    fully_covers_box: bool


def open_environment(source: dict[str, Any]) -> rasterio.Env:
    """Return a GDAL environment tuned for range reads of a remote GeoTIFF."""
    return rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_TIMEOUT=str(source["request_timeout_seconds"]),
        GDAL_HTTP_MAX_RETRY=str(source["http_max_retry"]),
    )


def remote_metadata(url: str, timeout_seconds: float) -> dict[str, str | None]:
    """Read the file date, ETag, and size from the server without downloading."""
    request = Request(url, method="HEAD")  # noqa: S310
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        headers = response.headers
        return {
            "last_modified": headers.get("Last-Modified"),
            "etag": headers.get("ETag"),
            "content_length": headers.get("Content-Length"),
        }


def box_window(src: Any, bbox: Box) -> tuple[Window, bool]:
    """Return the pixel window around a lon/lat box and whether it fits the raster.

    The window is padded by one pixel so every pixel centre inside the box is
    read. The flag is False when the raster edge cuts the box (partial cover).
    """
    bounds = transform_bounds(WGS84, src.crs, *bbox)
    window = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
    padded = Window(
        window.col_off - 1, window.row_off - 1, window.width + 2, window.height + 2
    )
    full = Window(0, 0, src.width, src.height)
    try:
        clipped = padded.intersection(full)
    except rasterio.errors.WindowError as error:
        raise ValueError("Study box does not intersect the raster") from error
    return clipped, clipped == padded


def inside_box_mask(
    transform: Affine, shape: tuple[int, int], crs: Any, bbox: Box
) -> np.ndarray:
    """Mark pixels whose centres fall inside the lon/lat box.

    The box is a rectangle in lon/lat, which is a slightly skewed shape in a
    projected CRS, so the test is done in lon/lat rather than on window edges.
    """
    rows, cols = np.meshgrid(
        np.arange(shape[0]) + 0.5, np.arange(shape[1]) + 0.5, indexing="ij"
    )
    xs = transform.a * cols + transform.b * rows + transform.c
    ys = transform.d * cols + transform.e * rows + transform.f
    lon, lat = Transformer.from_crs(crs, WGS84, always_xy=True).transform(xs, ys)
    west, south, east, north = bbox
    return (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)


def count_valid_by_year(
    data: np.ndarray,
    inside: np.ndarray,
    years: list[int],
    nodata: float,
    pixel_area_m2: float,
    scale_to_m: float,
) -> list[dict[str, Any]]:
    """Count non-nodata pixels inside the box for each year band in `data`."""
    box_pixels = int(inside.sum())
    records = []
    for year, band in zip(years, data, strict=True):
        valid = inside & (band != nodata)
        heights = band[valid].astype(float) * scale_to_m
        record: dict[str, Any] = {
            "year": year,
            "box_pixels": box_pixels,
            "valid_pixels": int(valid.sum()),
            "valid_share": float(valid.sum() / box_pixels) if box_pixels else 0.0,
            "valid_area_km2": float(valid.sum() * pixel_area_m2 / 1e6),
        }
        if heights.size:
            low, median, high, top = np.percentile(heights, [0, 50, 95, 100])
            record["height_m"] = {
                name: round(float(value), 2)
                for name, value in zip(
                    ("min", "median", "p95", "max"),
                    (low, median, high, top),
                    strict=True,
                )
            }
        records.append(record)
    return records


def count_abrupt_changes(
    data: np.ndarray,
    inside: np.ndarray,
    years: list[int],
    nodata: float,
    threshold_m: float,
    scale_to_m: float,
) -> list[dict[str, Any]]:
    """Count large one-step height drops and gains between consecutive bands.

    Only changes strictly larger than the threshold count. Drops are expected
    from fire or logging; large gains are not. This ratio is the evidence that
    bands run forward in time.
    """
    # Compare in stored integer units so a change of exactly the threshold is
    # never counted because of floating-point rounding.
    threshold_raw = threshold_m / scale_to_m
    records = []
    for index in range(len(years) - 1):
        before, after = data[index], data[index + 1]
        both_valid = inside & (before != nodata) & (after != nodata)
        change = after.astype(np.int64) - before.astype(np.int64)
        records.append(
            {
                "from_year": years[index],
                "to_year": years[index + 1],
                "drop_pixels": int((both_valid & (change < -threshold_raw)).sum()),
                "gain_pixels": int((both_valid & (change > threshold_raw)).sum()),
            }
        )
    return records


def validate_raster(src: Any, source: dict[str, Any]) -> None:
    """Fail early when the raster does not match the configured band layout."""
    require_keys(source, REQUIRED_KEYS)
    if src.count != len(source["band_years"]):
        msg = f"Raster has {src.count} bands, config lists {len(source['band_years'])}"
        raise ValueError(msg)
    if src.nodata != source["nodata_value"]:
        msg = f"Raster nodata {src.nodata} differs from config {source['nodata_value']}"
        raise ValueError(msg)


def read_box(src: Any, bbox: Box) -> BoxRead:
    """Read every band over the study box and mark pixels inside it."""
    window, fully_covers_box = box_window(src, bbox)
    transform = src.window_transform(window)
    data = src.read(window=window)
    inside = inside_box_mask(transform, data.shape[1:], src.crs, bbox)
    return BoxRead(data, window, transform, inside, fully_covers_box)


def build_report(src: Any, box: BoxRead, source: dict[str, Any]) -> dict[str, Any]:
    """Summarize usable pixels per requested year and band-order evidence."""
    band_years = list(source["band_years"])
    check_years = list(source["check_years"])
    present = [year for year in check_years if year in band_years]
    indexes = [band_years.index(year) for year in present]
    pixel_area_m2 = abs(src.res[0] * src.res[1])
    scale = source["height_scale_to_m"]
    return {
        "citation": source.get("citation"),
        "tile_url": source["tile_url"],
        "raster_crs": str(src.crs),
        "study_crs": WGS84,
        "pixel_size_m": list(src.res),
        "nodata_value": src.nodata,
        "band_years_assumed": band_years,
        "raster_footprint_covers_box": box.fully_covers_box,
        "years_missing_from_product": sorted(set(check_years) - set(band_years)),
        "per_year": count_valid_by_year(
            box.data[indexes], box.inside, present, src.nodata, pixel_area_m2, scale
        ),
        "abrupt_changes": count_abrupt_changes(
            box.data,
            box.inside,
            band_years,
            src.nodata,
            source["abrupt_change_m"],
            scale,
        ),
    }


def write_box_copy(src: Any, box: BoxRead, output: Path) -> Path:
    """Save the box window as a small local GeoTIFF with all bands."""
    profile = src.profile.copy()
    profile.update(
        width=box.data.shape[2],
        height=box.data.shape[1],
        transform=box.transform,
        compress="lzw",
    )
    with rasterio.open(ensure_parent(output), "w", **profile) as destination:
        destination.write(box.data)
    return output
