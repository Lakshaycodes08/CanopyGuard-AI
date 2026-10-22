"""Turn an Earth Engine export of the ECHOSAT drop share into the compact copy.

The export is a one-band uint8 GeoTIFF on the 90 m grid (whole percent, 255 for
no data). The file is checked against the grid this repository derives for the
region before it is accepted.
"""

from __future__ import annotations

import argparse

import numpy as np
import rasterio
from pyproj import Transformer

from canopyguard.config import load_config, load_region
from canopyguard.data.landsat_stac import study_grid
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def expected_grid(region: dict, landsat: dict, factor: int) -> tuple:
    """Left, top, block size and shape of the 90 m grid for a region."""
    west, south, east, north = region["bbox"]
    to_utm = Transformer.from_crs("EPSG:4326", landsat["grid_crs"], always_xy=True)
    x0, y0 = to_utm.transform(west, south)
    x1, y1 = to_utm.transform(east, north)
    left, top, width, height = study_grid((x0, y0, x1, y1), landsat)
    size = float(landsat["grid_resolution_m"]) * factor
    return left, top, size, (height // factor, width // factor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    region = load_region(args.region)
    ingestion = load_config("configs/ingestion.yaml")
    source = ingestion["echosat_drop"]
    factor = int(source["compact_factor"])
    left, top, size, shape = expected_grid(region, ingestion["landsat"], factor)
    with rasterio.open(args.file) as src:
        percent = src.read(1)
        transform = src.transform
        crs = str(src.crs)
    if crs != ingestion["landsat"]["grid_crs"]:
        raise ValueError(f"Expected {ingestion['landsat']['grid_crs']}, got {crs}")
    if percent.dtype != np.uint8 or percent.shape != shape:
        raise ValueError(f"Expected uint8 {shape}, got {percent.dtype} {percent.shape}")
    if abs(transform.c - left) > 1e-3 or abs(transform.f - top) > 1e-3:
        raise ValueError(f"Origin {transform.c}, {transform.f} != {left}, {top}")
    if abs(transform.a - size) > 1e-6 or abs(transform.e + size) > 1e-6:
        raise ValueError(f"Pixel size {transform.a} is not {size}")
    output = ensure_parent(
        with_region(data_path(source["compact_output"]), region["suffix"])
    )
    np.savez_compressed(output, percent=percent, factor=factor)
    write_provenance(
        output,
        source_url="Earth Engine asset projects/ai4forest/assets/echosat",
        script_name="scripts/import_echosat_percent.py",
        bbox_wgs84=region["bbox"],
        crs=crs,
        row_count=1,
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    valid = percent != 255
    print(
        f"{region['name']}: {percent.shape} blocks, {valid.mean():.2f} valid, "
        f"mean drop {percent[valid].mean() / 100:.4f} -> {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
