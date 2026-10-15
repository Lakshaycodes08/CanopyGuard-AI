"""Write wire suspect flags and the near-line max/p95 exclusion per cell."""

import argparse
from pathlib import Path

import yaml

from canopyguard.lidar.wire_flags import run_flags


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/lidar.yaml")
    args = parser.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["wire_check"]
    run_flags(cfg)


if __name__ == "__main__":
    main()
