from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from run_noise_floor import _build_job, _build_log, _guard_plan, _signature

from canopyguard.config import load_config
from canopyguard.lidar.change import measure_pair
from canopyguard.lidar.plan import change_plan, pair_projects, resource_footprints


def main() -> int:
    config = load_config("configs/lidar.yaml")
    pairs = ["-".join(pair) for pair in config["change"]["pairs"]]

    parser = argparse.ArgumentParser(
        description="Build surfaces for a long-baseline pair and measure its change."
    )
    parser.add_argument("--pair", choices=pairs, default=pairs[0])
    parser.add_argument("--tiles", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="/content/change")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    pair = tuple(args.pair.split("-"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bbox = load_config("configs/study_area.yaml")["study_area"]["bbox"]
    study_box = tuple(float(bbox[key]) for key in ("west", "south", "east", "north"))
    footprints = _footprints(config, pair, out)
    count = args.tiles or int(config["change"]["tile_count"])
    plan = change_plan(config, study_box, pair, footprints, count, args.seed)
    config["harmonization"]["sample_radius_m"] = plan["sample_radius_m"]
    plan["build_signature"] = _signature(plan, config)
    _guard_plan(out, plan)

    print(f"pair {args.pair}")
    for epoch, names in sorted(plan["projects"].items()):
        print(f"epoch {epoch} resources {', '.join(names)}")
    print(
        f"candidates {plan['candidate_tiles']} tiles of "
        f"{plan['tile_size_m']:.0f} m, {plan['candidate_area_km2']:.1f} km2"
    )
    print(f"drawn {plan['tile_count']} tiles, {plan['sample_area_km2']:.1f} km2")
    print(f"sampling radius {plan['sample_radius_m']:.4f} m")
    print("\ntile epoch      retained          ground   ground%   scan angle")

    previous = _build_log(out)
    jobs = [
        (tile, epoch, readers, out, config, previous)
        for tile in plan["tiles"]
        for epoch, readers in sorted(tile["readers"].items())
    ]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            built = list(pool.map(_build_job, jobs))
    else:
        built = [_build_job(job) for job in jobs]
    merged = {**previous}
    for entry in built:
        merged[(int(entry["tile"]), str(entry["epoch"]))] = entry
    (out / "build_log.json").write_text(
        json.dumps(list(merged.values()), indent=2), encoding="utf-8"
    )

    result = measure_pair(plan, out, pair, config)
    (out / f"change_{args.pair}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _report(result)
    return 0


def _footprints(config: dict, pair: tuple[str, ...], out: Path) -> dict[str, list]:
    """Read each resource manifest once and keep it beside the surfaces."""
    cache = out / "footprints.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    projects = pair_projects(config, pair)
    missing = {
        epoch: [name for name in names if name not in cached]
        for epoch, names in projects.items()
    }
    fetched = resource_footprints(missing)
    if fetched:
        cached.update(fetched)
        cache.write_text(json.dumps(cached), encoding="utf-8")
    else:
        print("footprints cached")
    for name in sorted({name for names in projects.values() for name in names}):
        print(f"resource {name} source files {len(cached[name]):>7,}")
    return cached


def _report(result: dict) -> None:
    epochs = result["pair"]
    shift = result["shift"]
    check = result["terrain_check"]
    print(
        f"\nterrain before co-registration: scale {check['scale']:.4f}, "
        f"offset {check['offset_m']:+.2f} m over {check['cells']:,.0f} cells"
    )
    admitted = [tile for tile in result["tiles"] if tile["admitted"]]
    print(f"\ntiles admitted {len(admitted)} of {len(result['tiles'])}")
    for tile in result["tiles"]:
        if not tile["admitted"]:
            print(f"  tile {tile['tile']:>4.0f} rejected: {tile['reason']}")

    print(f"\nbaseline {result['baseline_years']:.2f} years")
    print(
        f"shift dx {shift['dx_m']:+.3f} dy {shift['dy_m']:+.3f} "
        f"dz {shift['dz_m']:+.3f} over {shift['tiles']:.0f} tiles, "
        f"{shift['iterations']:.0f} iterations, "
        f"terrain rmse {shift['rmse_before_m']:.3f} -> {shift['rmse_after_m']:.3f} m"
    )

    header = "".join(f"{epoch + ' median_h':>16}{'p95_h':>8}" for epoch in epochs)
    print(f"\ntile {header}")
    for entry in result["heights"]:
        parts = []
        for epoch in epochs:
            summary = entry[epoch]
            if not summary.get("cells"):
                parts.append(f"{'':>16}{'':>8}")
                continue
            parts.append(f"{summary['median_m']:>16.2f}{summary['p95_m']:>8.2f}")
        print(f"{entry['tile']:>4.0f} " + "".join(parts))

    floor = result["bare_floor"]
    print(
        f"\nbare floor cells {floor['cells']:,.0f} mean {floor['mean_m']:+.3f} "
        f"median {floor['median_m']:+.3f} nmad {floor['nmad_m']:.3f} m"
    )
    moved = result["disturbance"]
    print(
        f"disturbance beyond {moved['limit_m']:.1f} m: "
        f"loss {moved['loss_fraction']:.2%} gain {moved['gain_fraction']:.2%} "
        f"of {moved['valid_cells']:,.0f} cells"
    )

    print(
        "\nscale_m      cells  median_all  signal_all  frac_all  "
        "median_canopy  signal_canopy  frac_canopy   lod95"
    )
    for row in result["surface"]:
        every, canopy = row["all"], row["canopy"]
        flag = "" if every["admitted"] else "  (few cells)"
        print(
            f"{row['scale_m']:>7.0f} {every['cells']:>10,.0f} "
            f"{every['median_change_m']:>+11.3f} {every['signal_m']:>11.3f} "
            f"{every['detectable_fraction']:>9.1%} "
            f"{canopy['median_change_m']:>+14.3f} {canopy['signal_m']:>14.3f} "
            f"{canopy['detectable_fraction']:>12.1%} {row['lod95_m']:>7.3f}{flag}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
