from __future__ import annotations

import argparse
import json
from pathlib import Path

from canopyguard.config import load_config
from canopyguard.lidar.chm import build_terrain_pipeline, run_pipeline
from canopyguard.lidar.noise_floor import measure, surface_paths
from canopyguard.lidar.plan import calibration_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build surfaces and measure the floor."
    )
    parser.add_argument("--tiles", type=int, default=40)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="/content/truth")
    args = parser.parse_args()

    config = load_config("configs/lidar.yaml")
    plan = calibration_plan(config, args.tiles, args.seed)
    config["harmonization"]["sample_radius_m"] = plan["sample_radius_m"]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{plan['tile_count']} tiles, {plan['sample_area_km2']:.1f} km2")
    print(f"sampling radius {plan['sample_radius_m']:.4f} m")

    build_log = [
        _build(tile, epoch, reader, out, config)
        for tile in plan["tiles"]
        for epoch, reader in sorted(tile["readers"].items())
    ]
    (out / "build_log.json").write_text(
        json.dumps(build_log, indent=2), encoding="utf-8"
    )

    result = measure(plan, out, config)
    (out / "noise_floor.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _report(result)
    return 0 if result["gate"]["passed"] else 1


def _build(tile, epoch: str, reader, out: Path, config) -> dict:
    paths = surface_paths(out, epoch, tile["index"])
    built = (paths[kind] for kind in ("dtm", "dsm"))
    if all(path.exists() and path.stat().st_size for path in built):
        print(f"tile {tile['index']:>4} {epoch} cached")
        return {"tile": tile["index"], "epoch": epoch, "points": -1, "note": "cached"}

    pipeline = build_terrain_pipeline(
        reader, str(paths["dtm"]), str(paths["dsm"]), config
    )
    try:
        points = run_pipeline(pipeline)
        note = ""
    except (RuntimeError, OSError) as error:
        points, note = 0, str(error)[:200]
    print(f"tile {tile['index']:>4} {epoch} points {points:>12,} {note}")
    return {"tile": tile["index"], "epoch": epoch, "points": points, "note": note}


def _report(result: dict) -> None:
    print("\nscale_m    sigma   lod95    mean        cells")
    for row in result["rows"]:
        print(
            f"{row['scale_m']:>7.0f} {row['sigma_m']:>8.3f} {row['lod95_m']:>7.3f} "
            f"{row['mean_m']:>+7.3f} {row['cells']:>12,.0f}"
        )
    print(f"\ndecay exponent {result['rows'][0]['decay_exponent']:.3f}")
    for name, passed in result["gate"]["checks"].items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    print(f"\nGATE {'PASS' if result['gate']['passed'] else 'FAIL'}")


if __name__ == "__main__":
    raise SystemExit(main())
