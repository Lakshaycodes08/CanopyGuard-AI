from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from canopyguard.config import load_config
from canopyguard.evaluation.bootstrap import excludes_zero, paired_block_bootstrap
from canopyguard.evaluation.metrics import bias, mae, r2, rmse
from canopyguard.evaluation.change_table import (
    cell_targets,
    flatten,
    optical_features,
    terrain_features,
)
from canopyguard.features.landsat import (
    BANDS,
    block_grid,
    pixel_grid_request,
    structured_to_stack,
    summer_composite,
    with_indices,
)
from canopyguard.lidar.gridio import read_grid
from canopyguard.lidar.noise_floor import surface_paths

FALLBACK_CRS = "EPSG:26910"
STATIC = [
    "start_h",
    "canopy_fraction",
    "elevation",
    "slope_deg",
    "northness",
    "eastness",
]


def main() -> int:
    config = load_config("configs/lidar.yaml")
    parser = argparse.ArgumentParser(
        description="Landsat predictors against LiDAR canopy change, grouped by tile."
    )
    parser.add_argument("--pair", default="2013-2022")
    parser.add_argument("--out", default="/content/change2")
    parser.add_argument("--project", required=True)
    parser.add_argument("--factor", type=int, default=30)
    parser.add_argument("--months", type=int, nargs=2, default=[6, 9])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--crs", default="EPSG:6339")
    args = parser.parse_args()

    first, last = (int(year) for year in args.pair.split("-"))
    out = Path(args.out)
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    rules = config["change"]
    cache = out / "landsat"
    cache.mkdir(exist_ok=True)

    import ee

    ee.Initialize(project=args.project)

    tables = []
    for tile in plan["tiles"]:
        index = int(tile["index"])
        start_paths = surface_paths(out, str(first), index)
        end_paths = surface_paths(out, str(last), index)
        if not (start_paths["chm"].exists() and end_paths["chm"].exists()):
            print(f"tile {index:>3} skipped: no canopy height rasters")
            continue
        chm_a, profile = read_grid(start_paths["chm"])
        chm_b, _ = read_grid(end_paths["chm"])
        dtm, _ = read_grid(start_paths["dtm"])
        resolution = float(profile["transform"][0])
        grid = block_grid(
            profile["transform"], chm_a.shape[1], chm_a.shape[0], args.factor
        )

        stacks = {}
        for year in range(first, last + 1):
            stacks[year] = _composite(ee, tile, grid, year, args, cache, index)
        columns = {
            **cell_targets(
                chm_a,
                chm_b,
                args.factor,
                0.5,
                float(rules["canopy_min_height_m"]),
                float(rules["disturbance_limit_m"]),
            ),
            **terrain_features(dtm, args.factor, resolution),
            **optical_features(stacks, first, last),
            "clear_start": stacks[first]["clear_count"],
            "clear_end": stacks[last]["clear_count"],
        }
        tables.append(flatten(index, columns))
        print(
            f"tile {index:>3} cells {grid['width'] * grid['height']:>4} "
            f"clear obs {np.nanmedian(stacks[first]['clear_count']):.0f} / "
            f"{np.nanmedian(stacks[last]['clear_count']):.0f}"
        )

    table = {key: np.concatenate([t[key] for t in tables]) for key in tables[0]}
    np.savez_compressed(out / f"optical_table_{args.pair}.npz", **table)
    result = _evaluate(table, rules, args.folds)
    (out / f"optical_skill_{args.pair}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _report(result)
    return 0


def _composite(ee, tile, grid, year, args, cache, index) -> dict:
    path = cache / f"t{index:04d}_{year}.npz"
    if path.exists():
        with np.load(path) as saved:
            return {key: saved[key] for key in saved.files}
    west, south, east, north = tile["box"]
    geometry = ee.Geometry.Rectangle([west, south, east, north])
    image = summer_composite(ee, geometry, year, tuple(args.months)).select(
        [*BANDS, "clear_count"]
    )
    try:
        array = _pixels(ee, image, grid, args.crs)
    except ee.EEException as error:
        if args.crs == FALLBACK_CRS or "rojection" not in str(error):
            raise
        print(f"{args.crs} refused ({error}); using {FALLBACK_CRS}")
        args.crs = FALLBACK_CRS
        array = _pixels(ee, image, grid, args.crs)
    stack = with_indices(structured_to_stack(array))
    np.savez_compressed(path, **stack)
    return stack


def _pixels(ee, image, grid, crs):
    return ee.data.computePixels(
        {
            "expression": image,
            "fileFormat": "NUMPY_NDARRAY",
            "grid": pixel_grid_request(grid, crs),
        }
    )


def _feature_sets(table: dict) -> dict[str, list[str]]:
    optical = sorted(
        key
        for key in table
        if key.endswith(("_start", "_end", "_diff", "_trend"))
        and not key.startswith("clear")
    )
    terrain = ["elevation", "slope_deg", "northness", "eastness"]
    return {
        "mean": [],
        "static": STATIC,
        "static_optical": STATIC + optical,
        "terrain_optical": terrain + optical,
    }


def _subsets(table: dict, rules: dict) -> dict[str, np.ndarray]:
    valid = np.isfinite(table["change"]) & np.isfinite(table["start_h"])
    canopy = (
        valid
        & (table["start_h"] >= float(rules["canopy_min_height_m"]))
        & (table["loss_fraction"] < 0.1)
    )
    return {"all": valid, "undisturbed_canopy": canopy}


def _predict(table, rows, features, folds) -> np.ndarray:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import GroupKFold

    y = table["change"][rows]
    groups = table["tile"][rows]
    x = np.column_stack([table[name][rows] for name in features] or [np.zeros(y.size)])
    splits = min(folds, np.unique(groups).size)
    predicted = np.full(y.shape, np.nan)
    for train, test in GroupKFold(n_splits=splits).split(x, y, groups):
        if not features:
            predicted[test] = float(np.mean(y[train]))
            continue
        model = HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, min_samples_leaf=20, random_state=0
        )
        model.fit(x[train], y[train])
        predicted[test] = model.predict(x[test])
    return predicted


def _evaluate(table: dict, rules: dict, folds: int) -> dict:
    sets = _feature_sets(table)
    result = {"folds": folds, "feature_sets": sets, "subsets": {}}
    for subset, rows in _subsets(table, rules).items():
        y = table["change"][rows]
        tiles = table["tile"][rows]
        entry = {"cells": int(rows.sum()), "tiles": int(np.unique(tiles).size)}
        entry["target_median_m"] = float(np.median(y))
        errors = {}
        for name, features in sets.items():
            predicted = _predict(table, rows, features, folds)
            errors[name] = predicted - y
            entry[name] = {
                "mae_m": mae(y, predicted),
                "rmse_m": rmse(y, predicted),
                "bias_m": bias(y, predicted),
                "r2": r2(y, predicted),
            }
        for challenger in ("static_optical", "terrain_optical"):
            test = paired_block_bootstrap(errors[challenger], errors["static"], tiles)
            test["optical_better"] = bool(excludes_zero(test) and test["ci_high"] < 0)
            entry[f"{challenger}_minus_static"] = test
        result["subsets"][subset] = entry
    return result


def _report(result: dict) -> None:
    for subset, entry in result["subsets"].items():
        print(
            f"\n{subset}: {entry['cells']:,} cells in {entry['tiles']} tiles, "
            f"median change {entry['target_median_m']:+.3f} m"
        )
        print(f"{'model':<18}{'mae':>8}{'rmse':>8}{'bias':>8}{'r2':>8}")
        for name in result["feature_sets"]:
            row = entry[name]
            print(
                f"{name:<18}{row['mae_m']:>8.3f}{row['rmse_m']:>8.3f}"
                f"{row['bias_m']:>+8.3f}{row['r2']:>8.3f}"
            )
        for challenger in ("static_optical", "terrain_optical"):
            test = entry[f"{challenger}_minus_static"]
            print(
                f"MAE {challenger} - static {test['difference']:+.3f} m, "
                f"95% CI [{test['ci_low']:+.3f}, {test['ci_high']:+.3f}] "
                f"over {test['blocks']:.0f} tiles: "
                f"{'optical better' if test['optical_better'] else 'no gain shown'}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
