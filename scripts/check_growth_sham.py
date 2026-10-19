from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.forecasting.growth_model import (
    feature_columns,
    out_of_fold_predictions,
    score,
)
from canopyguard.forecasting.region_transfer import (
    apply_screen,
    far_from_other_regions,
    noise_columns,
    region_codes,
    shuffle_within_region,
    stack_regions,
    utm_box,
)
from canopyguard.io import data_path, project_root, with_region
from canopyguard.utils import set_seeds


def main() -> int:
    config = load_config("configs/growth.yaml")
    settings = config["sham_check"]
    seed = int(config["seed"])
    set_seeds(seed)
    crs = load_config("configs/ingestion.yaml")["landsat"]["grid_crs"]
    names = config["regions"]["names"]
    regions = {n: load_region(n) for n in names}
    boxes = {n: utm_box(r["bbox"], crs) for n, r in regions.items()}
    base = data_path(config["table"]["output"])
    tables = {}
    for name in names:
        path = with_region(base, regions[name]["suffix"])
        path = path.with_name(f"{path.stem}_x{settings['scale']}{path.suffix}")
        tables[name] = pd.read_parquet(path).dropna(subset=["mean_change"])
    stacked = stack_regions(tables).reset_index(drop=True)
    table = apply_screen(stacked, config["screens"][settings["screen"]])
    table = table.reset_index(drop=True)
    columns = feature_columns(
        table, config["model"]["feature_sets"][settings["feature_set"]]
    )
    scored = far_from_other_regions(table, boxes, float(config["regions"]["buffer_m"]))
    folds = region_codes(table, names)
    variants = {
        "real": table,
        "shuffled_within_region": shuffle_within_region(table, columns, seed),
        "noise": noise_columns(table, columns, seed),
    }
    y = table["mean_change"].to_numpy()
    report: dict = {
        "screen": settings["screen"],
        "feature_set": settings["feature_set"],
    }
    for label, data in variants.items():
        held_out = out_of_fold_predictions(
            data, columns, "mean_change", folds, config["model"]["lightgbm"], seed
        )
        for model in ("model", "train_mean"):
            if label != "real" and model == "train_mean":
                continue
            key = f"{label}" if model == "model" else "train_mean_baseline"
            report[key] = {
                name: score(
                    y[(table["region"] == name).to_numpy() & scored],
                    held_out[model][(table["region"] == name).to_numpy() & scored],
                )
                for name in names
            }
        print(label, {n: round(report[label][n]["mae"], 3) for n in names}, flush=True)
    print(
        "train_mean",
        {n: round(report["train_mean_baseline"][n]["mae"], 3) for n in names},
    )
    lod = load_config("configs/lidar.yaml")["noise_floor"]["measured"]
    report["lidar_noise"] = {
        "sigma_30m": lod["sigma_m"][30],
        "lod95_30m": lod["lod95_m"][30],
        "mae_floor_from_noise_alone": 0.798 * lod["sigma_m"][30],
    }
    output = project_root() / settings["output"]
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
