from __future__ import annotations

import argparse

import numpy as np
from pyproj import Transformer

from canopyguard.config import load_config, load_region
from canopyguard.data.echosat_drop import compact_percent, drop_share_on_grid
from canopyguard.data.landsat_stac import study_grid
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    ingestion = load_config("configs/ingestion.yaml")
    source = {**ingestion["echosat"], **ingestion["echosat_drop"]}
    suffix = region["suffix"]
    landsat = ingestion["landsat"]
    west, south, east, north = region["bbox"]
    to_utm = Transformer.from_crs("EPSG:4326", landsat["grid_crs"], always_xy=True)
    x0, y0 = to_utm.transform(west, south)
    x1, y1 = to_utm.transform(east, north)
    left, top, width, height = study_grid((x0, y0, x1, y1), landsat)
    grid = (left, top, float(landsat["grid_resolution_m"]), width, height)
    share = drop_share_on_grid(source, region["bbox"], grid)
    output = ensure_parent(with_region(data_path(source["output"]), suffix))
    np.savez_compressed(output, echosat_drop_share=share)
    compact = ensure_parent(with_region(data_path(source["compact_output"]), suffix))
    factor = int(source["compact_factor"])
    np.savez_compressed(compact, percent=compact_percent(share, factor), factor=factor)
    for path in (output, compact):
        write_provenance(
            path,
            source_url=source["tile_url"],
            script_name="scripts/ingest_echosat_drop.py",
            bbox_wgs84=region["bbox"],
            crs="EPSG:32610",
            row_count=1,
            config_sha256=file_sha256("configs/ingestion.yaml"),
        )
    valid = np.isfinite(share)
    print(
        f"{region['name']}: valid {valid.mean():.2f}, "
        f"mean drop share {np.nanmean(share):.4f} -> {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
