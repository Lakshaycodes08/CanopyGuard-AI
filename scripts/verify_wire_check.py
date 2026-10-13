"""Run placebo, persistence and sensitivity checks for the wire check."""

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from canopyguard.lidar.wire_check import analysis_rows
from canopyguard.lidar.wire_check_run import line_distance
from canopyguard.lidar.wire_check_verify import run_verification


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/lidar.yaml")
    args = parser.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["wire_check"]
    table = dict(np.load(cfg["labels_path"]))
    rows, _ = analysis_rows(table)
    dist = line_distance(cfg["lines_path"], table["x"][rows], table["y"][rows])
    result = run_verification(table, rows, dist, cfg["lines_path"], cfg)
    out = Path(cfg["out_dir"]) / "verification.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
