from __future__ import annotations

import argparse
import json
from pathlib import Path

from canopyguard.config import load_config
from canopyguard.lidar.chm import build_terrain_pipeline, run_pipeline
from canopyguard.lidar.noise_floor import measure, surface_paths
from canopyguard.lidar.plan import calibration_plan, noise_floor_footprints


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build surfaces and measure the floor."
    )
    parser.add_argument("--tiles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="/content/truth")
    args = parser.parse_args()

    config = load_config("configs/lidar.yaml")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    footprints = _footprints(config, out)
    count = args.tiles or int(config["tiers"]["sample_tile_count"])
    plan = calibration_plan(config, count, footprints, args.seed)
    config["harmonization"]["sample_radius_m"] = plan["sample_radius_m"]
    _guard_plan(out, plan)

    print(
        f"co-covered {plan['candidate_tiles']} tiles of "
        f"{plan['tile_size_m']:.0f} m, {plan['candidate_area_km2']:.1f} km2"
    )
    print(f"drawn {plan['tile_count']} tiles, {plan['sample_area_km2']:.1f} km2")
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


def _guard_plan(out: Path, plan: dict) -> None:
    """Refuse to reuse surfaces that were built for different tiles.

    Surfaces are named by tile index, so a changed tile list would silently
    read the previous run's rasters.
    """
    saved = out / "plan.json"
    stale = f"{out} holds surfaces for other tiles; use a new --out"
    if saved.exists():
        previous = json.loads(saved.read_text(encoding="utf-8"))
        boxes = [tile["box"] for tile in previous.get("tiles", [])]
        if boxes != [tile["box"] for tile in plan["tiles"]]:
            raise SystemExit(stale)
    elif any(out.glob("dtm_*.tif")):
        raise SystemExit(stale)
    saved.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _footprints(config, out: Path) -> dict[str, list]:
    """Read the source manifests once and keep them beside the surfaces."""
    cache = out / "footprints.json"
    if cache.exists():
        print("footprints cached")
        return json.loads(cache.read_text(encoding="utf-8"))

    footprints = noise_floor_footprints(config)
    cache.write_text(json.dumps(footprints), encoding="utf-8")
    for epoch, boxes in sorted(footprints.items()):
        print(f"epoch {epoch} source files {len(boxes):>7,}")
    return footprints


def _build(tile, epoch: str, reader, out: Path, config) -> dict:
    paths = surface_paths(out, epoch, tile["index"])
    built = (paths[kind] for kind in ("dtm", "dsm"))
    if all(path.exists() and path.stat().st_size for path in built):
        print(f"tile {tile['index']:>4} {epoch} cached")
        return {"tile": tile["index"], "epoch": epoch, "points": -1, "note": "cached"}

    pipeline = build_terrain_pipeline(
        reader, str(paths["dtm"]), str(paths["dsm"]), tile["grid"], config
    )
    try:
        points = run_pipeline(pipeline)
        note = ""
    except (RuntimeError, OSError) as error:
        points, note = 0, str(error)[:200]
    print(f"tile {tile['index']:>4} {epoch} points {points:>12,} {note}")
    return {"tile": tile["index"], "epoch": epoch, "points": points, "note": note}


def _report(result: dict) -> None:
    shift = result["shift"]
    print(
        f"\nshift dx {shift['dx_m']:+.3f} dy {shift['dy_m']:+.3f} "
        f"dz {shift['dz_m']:+.3f} over {shift['tiles']:.0f} tiles, "
        f"{shift['cells']:,.0f} cells, {shift['iterations']:.0f} iterations"
    )
    print(
        f"terrain rmse {shift['rmse_before_m']:.3f} -> {shift['rmse_after_m']:.3f} m"
    )
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
