from __future__ import annotations

import argparse
import json

from canopyguard.config import load_config, load_region
from canopyguard.data.frap_fires import fetch_perimeters
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    config = load_config("configs/ingestion.yaml")["frap_fires"]
    perimeters = fetch_perimeters(region["bbox"], config)
    output = ensure_parent(with_region(data_path(config["output"]), region["suffix"]))
    output.write_text(json.dumps(perimeters) + "\n", "utf-8")
    write_provenance(
        output,
        source_url=config["url"],
        script_name="scripts/ingest_fire_perimeters.py",
        bbox_wgs84=region["bbox"],
        crs="EPSG:4326",
        row_count=len(perimeters["features"]),
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"{len(perimeters['features'])} perimeters -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
