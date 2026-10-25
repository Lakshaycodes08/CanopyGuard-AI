"""Copy a finished region label build into data/processed with provenance."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from canopyguard.config import load_config, load_region
from canopyguard.io import data_path, ensure_parent, regional_path
from canopyguard.provenance import file_sha256, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--build-dir", required=True)
    args = parser.parse_args()
    region = load_region(args.region)
    config = load_config("configs/lidar.yaml")
    box_text = " ".join(map(str, region["bbox"]))
    first, last = region["pair"]
    source = Path(args.build_dir) / f"labels_{first}-{last}_unique.npz"
    target = ensure_parent(
        regional_path(
            data_path(config["label_archive"]["unique"].removeprefix("data/")), region
        )
    )
    shutil.copyfile(source, target)
    write_provenance(
        target,
        source_url=f"local: scripts/run_change.py --box {box_text}",
        script_name="scripts/run_change.py",
        bbox_wgs84=region["bbox"],
        crs="EPSG:6339",
        config_sha256=file_sha256("configs/lidar.yaml"),
    )
    print(f"Registered {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
