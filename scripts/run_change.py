from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from run_noise_floor import _build_log, _checkpointed_build, _guard_plan, _signature

from canopyguard.config import load_config
from canopyguard.data.osm_power import fetch_power_lines, parse_overpass, spans
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
    parser.add_argument("--corridor", action="store_true")
    parser.add_argument("--lines", default=None)
    args = parser.parse_args()

    pair = tuple(args.pair.split("-"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    bbox = load_config("configs/study_area.yaml")["study_area"]["bbox"]
    study_box = tuple(float(bbox[key]) for key in ("west", "south", "east", "north"))
    footprints = _footprints(config, pair, out)
    count = args.tiles or int(config["change"]["tile_count"])
    corridor = None
    if args.corridor:
        lines = _power_lines(config, study_box, out, args.lines)
        corridor = (lines, float(config["change"]["corridor_buffer_m"]))
        count = args.tiles if args.tiles is not None else int(
            config["change"]["background_tiles"]
        )
    plan = change_plan(
        config, study_box, pair, footprints, count, args.seed, corridor=corridor
    )
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
    print(
        f"drawn {plan['tile_count']} tiles ({plan['required_tiles']} on corridors), "
        f"{plan['sample_area_km2']:.1f} km2"
    )
    print(f"sampling radius {plan['sample_radius_m']:.4f} m")
    print("\ntile epoch      retained          ground   ground%   scan angle")

    previous = _build_log(out)
    jobs = [
        (tile, epoch, readers, out, config, previous)
        for tile in plan["tiles"]
        for epoch, readers in sorted(tile["readers"].items())
    ]
    _checkpointed_build(out, previous, jobs, args.workers)

    result = measure_pair(plan, out, pair, config)
    labels = result.pop("labels")
    if labels:
        np.savez_compressed(out / f"labels_{args.pair}.npz", **labels)
        print(f"labels {labels['cell_id'].size:,} cells written")
    (out / f"change_{args.pair}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _report(result)
    return 0


def _power_lines(
    config: dict, study_box: tuple, out: Path, source: str | None
) -> list[dict]:
    """OpenStreetMap power lines in the study box, fetched once and cached.

    A saved Overpass response given with --lines is used without network
    access, and so is the copy kept beside the surfaces after a first fetch.
    """
    cache = out / "power_lines.json"
    kinds = tuple(config["change"]["power_kinds"])
    if source:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
        cache.write_text(json.dumps(payload), encoding="utf-8")
    elif cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        payload = fetch_power_lines(study_box, kinds)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    lines = parse_overpass(payload)
    pieces = spans(lines)
    (out / "spans.json").write_text(json.dumps(pieces), encoding="utf-8")
    print(f"power lines {len(lines)}, spans {len(pieces)}")
    return lines


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
