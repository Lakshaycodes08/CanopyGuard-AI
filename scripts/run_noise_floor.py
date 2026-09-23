from __future__ import annotations

import argparse
import hashlib
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
    plan["build_signature"] = _signature(plan, config)
    _guard_plan(out, plan)

    print(
        f"co-covered {plan['candidate_tiles']} tiles of "
        f"{plan['tile_size_m']:.0f} m, {plan['candidate_area_km2']:.1f} km2"
    )
    print(f"drawn {plan['tile_count']} tiles, {plan['sample_area_km2']:.1f} km2")
    print(f"sampling radius {plan['sample_radius_m']:.4f} m")
    print("\ntile epoch      retained          ground   ground%   scan angle")

    previous = _build_log(out)
    build_log = [
        _build(tile, epoch, reader, out, config, previous)
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
    _report(result, tuple(config["noise_floor"]["epoch_pair"]))
    return 0 if result["gate"]["passed"] else 1


def _signature(plan: dict, config: dict) -> str:
    """Digest of everything that decides what a surface contains.

    Surfaces are named by tile index, so a changed tile list, sampling radius
    or pipeline setting would otherwise be answered from the previous run's
    rasters.
    """
    material = {
        "boxes": [tile["box"] for tile in plan["tiles"]],
        "grids": [tile["grid"] for tile in plan["tiles"]],
        "harmonization": config["harmonization"],
        "chm": config["chm"],
    }
    payload = json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _guard_plan(out: Path, plan: dict) -> None:
    """Refuse to reuse surfaces that were not built the same way."""
    saved = out / "plan.json"
    stale = f"{out} holds surfaces built differently; use a new --out"
    if saved.exists():
        previous = json.loads(saved.read_text(encoding="utf-8"))
        if previous.get("build_signature") != plan["build_signature"]:
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


def _build_log(out: Path) -> dict[tuple[int, str], dict]:
    """Recorded outcome of a previous build, keyed by tile and epoch."""
    log = out / "build_log.json"
    if not log.exists():
        return {}
    return {
        (int(entry["tile"]), str(entry["epoch"])): entry
        for entry in json.loads(log.read_text(encoding="utf-8"))
    }


def _build(tile, epoch: str, reader, out: Path, config, previous: dict) -> dict:
    """Build one epoch of one tile, or report the recorded previous result.

    A tile that produced no point still leaves a raster on disk, so the cache
    test is the recorded point count rather than the presence of a file.
    """
    paths = surface_paths(out, epoch, tile["index"])
    done = previous.get((tile["index"], epoch))
    built = all(path.exists() and path.stat().st_size for path in
                (paths["dtm"], paths["dsm"]))
    if built and done and done.get("ground_points", 0) > 0:
        print(f"{tile['index']:>4} {epoch}  cached")
        return done

    pipeline = build_terrain_pipeline(
        reader, str(paths["dtm"]), str(paths["dsm"]), tile["grid"], config
    )
    entry = {"tile": tile["index"], "epoch": epoch, "note": ""}
    try:
        outcome = run_pipeline(pipeline)
        stats = outcome["stats"]
        retained = int(stats.get("Z", {}).get("count", 0))
        angle = stats.get("ScanAngleRank", {})
        entry.update(
            ground_points=outcome["points"],
            retained_points=retained,
            ground_fraction=outcome["points"] / retained if retained else 0.0,
            scan_angle_min=angle.get("minimum"),
            scan_angle_max=angle.get("maximum"),
            gps_time=stats.get("GpsTime", {}),
        )
    except (RuntimeError, OSError) as error:
        entry.update(ground_points=0, retained_points=0, note=str(error)[:160])

    angle_span = (
        f"{entry.get('scan_angle_min', 0):+.1f} to {entry.get('scan_angle_max', 0):+.1f}"
        if entry.get("scan_angle_max") is not None
        else ""
    )
    print(
        f"{tile['index']:>4} {epoch}  {entry['retained_points']:>12,} "
        f"{entry['ground_points']:>14,}  {entry.get('ground_fraction', 0):>7.1%}   "
        f"{angle_span} {entry['note']}"
    )
    return entry


def _report(result: dict, epochs: tuple[str, str]) -> None:
    shift = result["shift"]
    admitted = [tile for tile in result["tiles"] if tile["admitted"]]
    print(f"\ntiles admitted {len(admitted)} of {len(result['tiles'])}")
    for tile in result["tiles"]:
        if not tile["admitted"]:
            print(f"  tile {tile['tile']:>4.0f} rejected: {tile['reason']}")

    print("\ntile   median_h    p95_h   above2m   above5m  above10m")
    for entry in result["heights"]:
        summary = entry[epochs[0]]
        if not summary.get("cells"):
            continue
        print(
            f"{entry['tile']:>4.0f} {summary['median_m']:>10.2f} "
            f"{summary['p95_m']:>8.2f} {summary['above_2m']:>9.1%} "
            f"{summary['above_5m']:>9.1%} {summary['above_10m']:>9.1%}"
        )

    print(
        f"\nshift dx {shift['dx_m']:+.3f} dy {shift['dy_m']:+.3f} "
        f"dz {shift['dz_m']:+.3f} over {shift['tiles']:.0f} tiles, "
        f"{shift['cells']:,.0f} cells, {shift['iterations']:.0f} iterations"
    )
    print(
        f"terrain rmse {shift['rmse_before_m']:.3f} -> {shift['rmse_after_m']:.3f} m"
    )

    print("\nscale_m    nmad       sd   lod95    mean        cells  rel_err  used")
    for row in result["rows"]:
        print(
            f"{row['scale_m']:>7.0f} {row['sigma_m']:>7.3f} "
            f"{row['sigma_plain_m']:>8.3f} {row['lod95_m']:>7.3f} "
            f"{row['mean_m']:>+7.3f} {row['cells']:>12,.0f} "
            f"{row['sigma_relative_error']:>7.1%}  {'yes' if row['admitted'] else 'no'}"
        )
    print(f"\nstable cells {result['stable_fraction']:.1%}")
    print(
        f"\ndecay exponent {result['rows'][0]['decay_exponent']:.3f} "
        f"over {result['rows'][0]['decay_scales']:.0f} scales"
    )
    for name, passed in result["gate"]["checks"].items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    print(f"\nGATE {'PASS' if result['gate']['passed'] else 'FAIL'}")


if __name__ == "__main__":
    raise SystemExit(main())
