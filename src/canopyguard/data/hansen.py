"""Read official Hansen Global Forest Change loss years at LiDAR cell centers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.windows import Window

from canopyguard.io import ensure_parent


def download_lossyear(url: str, path: Path) -> None:
    """Keep the versioned official tile so the screen can be rerun offline."""
    if path.exists():
        return
    part = ensure_parent(path.with_suffix(path.suffix + ".part"))
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with part.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=1 << 20):
                if chunk:
                    stream.write(chunk)
    part.replace(path)


def loss_year_at_cells(
    path: Path, x: np.ndarray, y: np.ndarray, first_year: int, last_year: int
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the source's loss-year band; distinguish no-loss from no-data."""
    longitude, latitude = Transformer.from_crs(6339, 4326, always_xy=True).transform(
        x, y
    )
    with rasterio.open(path) as source:
        if source.crs.to_epsg() != 4326:
            raise ValueError("Expected the official Hansen tile in EPSG:4326")
        affine = source.transform
        if affine.b or affine.d:
            raise ValueError("Rotated Hansen raster is unsupported")
        column = np.floor((longitude - affine.c) / affine.a).astype(np.int64)
        row = np.floor((latitude - affine.f) / affine.e).astype(np.int64)
        inside = (
            (column >= 0) & (column < source.width) & (row >= 0) & (row < source.height)
        )
        if not inside.any():
            raise ValueError("No study cells fall inside the Hansen tile")
        left, right = int(column[inside].min()), int(column[inside].max()) + 1
        top, bottom = int(row[inside].min()), int(row[inside].max()) + 1
        window = Window(left, top, right - left, bottom - top)
        values = source.read(1, window=window)
        mask = source.read_masks(1, window=window)
    sample_row = np.clip(row - top, 0, values.shape[0] - 1)
    sample_col = np.clip(column - left, 0, values.shape[1] - 1)
    valid = inside & (mask[sample_row, sample_col] > 0)
    year = values[sample_row, sample_col]
    lost = valid & (year >= first_year - 2000) & (year <= last_year - 2000)
    return lost, valid
