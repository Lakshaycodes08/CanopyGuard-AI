"""Run the wire and tower label check (issue 6) and write results."""

import argparse
from pathlib import Path

import yaml

from canopyguard.lidar.wire_check_report import write_outputs
from canopyguard.lidar.wire_check_run import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/lidar.yaml")
    args = parser.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["wire_check"]
    results = run(cfg, cfg["labels_path"], cfg["lines_path"])
    write_outputs(results, cfg["labels_path"], cfg, cfg["out_dir"])


if __name__ == "__main__":
    main()
