from __future__ import annotations

import argparse

import numpy as np

from canopyguard.config import load_config, load_region
from canopyguard.data.echosat_drop import drop_share_on_grid
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    ingestion = load_config("configs/ingestion.yaml")
    source = {**ingestion["echosat"], **ingestion["echosat_drop"]}
    suffix = region["suffix"]
    composites = np.load(
        with_region(data_path(ingestion["landsat"]["output_composites"]), suffix)
    )
    left, top, step, width, height = composites["grid"]
    grid = (float(left), float(top), float(step), int(width), int(height))
    share = drop_share_on_grid(source, region["bbox"], grid)
    output = ensure_parent(with_region(data_path(source["output"]), suffix))
    np.savez_compressed(output, echosat_drop_share=share)
    write_provenance(
        output,
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
