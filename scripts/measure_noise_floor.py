from __future__ import annotations

import argparse
import json

from canopyguard.config import load_config
from canopyguard.evaluation.detectability import noise_floor_table
from canopyguard.io import data_path, ensure_parent
from canopyguard.lidar.difference import difference_ladder
from canopyguard.lidar.gridio import read_grid


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the change noise floor.")
    parser.add_argument("start_chm")
    parser.add_argument("end_chm")
    parser.add_argument("--stable-mask", default=None)
    args = parser.parse_args()

    lidar_config = load_config("configs/lidar.yaml")
    aggregation = lidar_config["aggregation"]
    base = lidar_config["chm"]["resolution_m"]

    start, _ = read_grid(args.start_chm)
    end, _ = read_grid(args.end_chm)
    if args.stable_mask:
        stable, _ = read_grid(args.stable_mask)
        start, end = _mask_pair(start, end, stable)

    ladder = difference_ladder(
        start, end, base, aggregation["scales_m"], aggregation["min_valid_fraction"]
    )
    rows = noise_floor_table(ladder, base_scale_m=base)

    output = ensure_parent(data_path("processed", "truth", "noise_floor.json"))
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))
    return 0


def _mask_pair(start, end, stable):
    import numpy as np

    keep = np.isfinite(stable) & (stable > 0)
    return np.where(keep, start, np.nan), np.where(keep, end, np.nan)


if __name__ == "__main__":
    raise SystemExit(main())
