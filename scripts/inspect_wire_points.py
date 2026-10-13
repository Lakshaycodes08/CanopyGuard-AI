"""Summarise raw LiDAR points in the suspect cells from the wire check."""

import argparse
from pathlib import Path

import yaml

from canopyguard.lidar.wire_inspect import inspect_cells


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/lidar.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    cfg = config["wire_check"]
    inspect_cells(
        f"{cfg['out_dir']}/suspects.csv",
        config,
        f"{cfg['out_dir']}/suspect_points_summary.csv",
        cfg["inspect"]["per_group"],
    )


if __name__ == "__main__":
    main()
