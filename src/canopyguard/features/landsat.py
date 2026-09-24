"""Landsat 8 surface reflectance composites on the canopy height grid.

Earth Engine is imported by the caller and passed in, so every function that
does not build an Earth Engine object is testable without it. Composites are
requested with an explicit affine grid whose upper left corner is the upper
left corner of the tile raster, so a Landsat cell covers exactly one block of
the canopy height grid and the block aggregation needs no resampling.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

COLLECTION = "LANDSAT/LC08/C02/T1_L2"
SOURCE_BANDS = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
BANDS = ["blue", "green", "red", "nir", "swir1", "swir2"]
INDICES = ["ndvi", "nbr", "ndmi"]
REFLECTANCE_SCALE = 0.0000275
REFLECTANCE_OFFSET = -0.2
QA_REJECT_BITS = 0b111110
FILL = -9999.0


def block_grid(
    transform: Any, width: int, height: int, factor: int
) -> dict[str, Any]:
    """Grid of cells that each cover `factor` by `factor` raster cells.

    `transform` is the north-up affine transform of the tile raster. Only
    whole blocks are kept, matching the block aggregation of the raster.
    """
    if factor < 1:
        raise ValueError("Block factor must be at least one")
    scale_x, shear_x, left = (float(transform[i]) for i in (0, 1, 2))
    shear_y, scale_y, top = (float(transform[i]) for i in (3, 4, 5))
    if shear_x or shear_y or scale_x <= 0 or scale_y >= 0:
        raise ValueError("Raster must be north up without rotation")
    columns = int(width) // factor
    rows = int(height) // factor
    if rows == 0 or columns == 0:
        raise ValueError("Block factor exceeds the raster extent")
    return {
        "width": columns,
        "height": rows,
        "scale_x": scale_x * factor,
        "scale_y": scale_y * factor,
        "left": left,
        "top": top,
    }


def pixel_grid_request(grid: dict[str, Any], crs: str) -> dict[str, Any]:
    """Grid description in the form the Earth Engine pixel endpoint takes."""
    return {
        "dimensions": {"width": int(grid["width"]), "height": int(grid["height"])},
        "affineTransform": {
            "scaleX": float(grid["scale_x"]),
            "shearX": 0.0,
            "translateX": float(grid["left"]),
            "shearY": 0.0,
            "scaleY": float(grid["scale_y"]),
            "translateY": float(grid["top"]),
        },
        "crsCode": crs,
    }


def reflectance(digital_number: ArrayLike) -> NDArray[np.float64]:
    """Collection 2 Level 2 surface reflectance from stored digital numbers."""
    values = np.asarray(digital_number, dtype=np.float64)
    return values * REFLECTANCE_SCALE + REFLECTANCE_OFFSET


def clear(qa_pixel: ArrayLike) -> NDArray[np.bool_]:
    """Pixels free of fill, dilated cloud, cirrus, cloud, shadow and snow."""
    qa = np.asarray(qa_pixel).astype(np.int64)
    return ((qa & QA_REJECT_BITS) == 0) & ((qa & 1) == 0)


def normalised_difference(left: ArrayLike, right: ArrayLike) -> NDArray[np.float64]:
    """(left - right) / (left + right), not-a-number where undefined."""
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    total = a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(total != 0, (a - b) / total, np.nan)


def with_indices(
    stack: dict[str, NDArray[np.float64]],
) -> dict[str, NDArray[np.float64]]:
    """Reflectance bands with NDVI, NBR and NDMI added."""
    missing = [band for band in BANDS if band not in stack]
    if missing:
        raise ValueError("Missing bands: " + ", ".join(missing))
    return {
        **stack,
        "ndvi": normalised_difference(stack["nir"], stack["red"]),
        "nbr": normalised_difference(stack["nir"], stack["swir2"]),
        "ndmi": normalised_difference(stack["nir"], stack["swir1"]),
    }


def summer_composite(
    ee: Any, geometry: Any, year: int, months: tuple[int, int]
) -> Any:
    """Median of clear Landsat 8 reflectance over the given months of a year."""
    start = ee.Date.fromYMD(int(year), int(months[0]), 1)
    end = ee.Date.fromYMD(int(year), int(months[1]), 1).advance(1, "month")

    def prepare(image: Any) -> Any:
        qa = image.select("QA_PIXEL")
        keep = qa.bitwiseAnd(QA_REJECT_BITS | 1).eq(0).And(
            image.select("QA_RADSAT").eq(0)
        )
        scaled = image.select(SOURCE_BANDS).multiply(REFLECTANCE_SCALE).add(
            REFLECTANCE_OFFSET
        )
        return scaled.rename(BANDS).updateMask(keep).resample("bilinear")

    collection = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(geometry)
        .filterDate(start, end)
        .map(prepare)
    )
    count = collection.select("nir").count().rename("clear_count")
    return collection.median().addBands(count).unmask(FILL)


def structured_to_stack(array: Any) -> dict[str, NDArray[np.float64]]:
    """Band dictionary from the structured array the pixel endpoint returns.

    Masked pixels arrive as the fill value and become not-a-number; a clear
    count of zero is kept as zero.
    """
    stack = {}
    for name in array.dtype.names:
        values = np.asarray(array[name], dtype=np.float64)
        if name == "clear_count":
            stack[name] = np.where(values == FILL, 0.0, values)
        else:
            stack[name] = np.where(values == FILL, np.nan, values)
    return stack
