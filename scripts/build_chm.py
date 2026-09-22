from __future__ import annotations

import argparse
import json

from canopyguard.config import load_config
from canopyguard.io import data_path, ensure_parent
from canopyguard.lidar.chm import (
    build_layer_pipeline,
    build_terrain_pipeline,
    run_pipeline,
)
from canopyguard.lidar.plan import calibration_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Build matched canopy surfaces.")
    parser.add_argument("--tiles", type=int, default=40)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config("configs/lidar.yaml")
    config["harmonization"]["sample_radius_m"] = None
    plan = calibration_plan(config, args.tiles, args.seed)
    config["harmonization"]["sample_radius_m"] = plan["sample_radius_m"]

    output = ensure_parent(data_path("interim", "lidar", "calibration_plan.json"))
    output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"{plan['tile_count']} tiles, {plan['sample_area_km2']:.1f} km2 -> {output}")
    if args.dry_run:
        return 0

    for tile in plan["tiles"]:
        for epoch, reader in sorted(tile["readers"].items()):
            _build_tile(reader, epoch, tile["index"], config)
    return 0


def _build_tile(reader, epoch: str, index: int, config) -> None:
    stem = f"{epoch}_t{index:04d}"
    terrain = build_terrain_pipeline(
        reader,
        str(data_path("processed", "truth", f"dtm_{stem}.tif")),
        str(data_path("processed", "truth", f"dsm_{stem}.tif")),
        config,
    )
    print(f"{stem} terrain points: {run_pipeline(terrain)}")
    for threshold in config["chm"]["pit_free_layers_m"]:
        layer = build_layer_pipeline(
            reader,
            str(data_path("processed", "truth", f"layer_{stem}_{threshold:g}.tif")),
            float(threshold),
            config,
        )
        run_pipeline(layer)


if __name__ == "__main__":
    raise SystemExit(main())
