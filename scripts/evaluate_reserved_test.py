from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.forecasting.growth_contrasts import bootstrap_pairs
from canopyguard.forecasting.growth_model import all_predictions, score
from canopyguard.forecasting.region_transfer import (
    apply_screen,
    load_region_tables,
    stack_regions,
)
from canopyguard.forecasting.reserved_test import (
    stack_train_test,
    stretch_predictions,
    years_between,
)
from canopyguard.io import data_path, ensure_parent, project_root, regional_path
from canopyguard.provenance import current_commit
from canopyguard.utils import set_seeds

START_HEIGHT_EDGES = [-1, 1, 5, 15, 30, 200]


def reserved_names() -> list[str]:
    regions = load_config("configs/regions.yaml")["regions"]
    return [n for n, r in regions.items() if r.get("reserved")]


def load_test_tables(config: dict, names: list[str], factor: int) -> dict:
    """Reserved-region tables with their 2013 to 2023 labels, no exclusions."""
    base = data_path(config["table"]["output"])
    tables = {}
    for name in names:
        path = regional_path(base, load_region(name))
        path = path.with_name(f"{path.stem}_x{factor}{path.suffix}")
        tables[name] = pd.read_parquet(path).dropna(subset=["mean_change"])
    return tables


def main() -> int:
    config = load_config("configs/growth.yaml")
    ingestion = load_config("configs/ingestion.yaml")
    settings = config["reserved_test"]
    seed = int(config["seed"])
    set_seeds(seed)
    crs = ingestion["landsat"]["grid_crs"]
    factor = int(settings["scale"])
    epochs = load_config("configs/lidar.yaml")["epochs"]
    ratio = years_between(epochs, ("2013", "2023")) / years_between(
        epochs, ("2013", "2022")
    )
    train = stack_regions(
        load_region_tables(config, config["regions"]["names"], factor, crs)
    )
    test_names = reserved_names()
    test = stack_regions(load_test_tables(config, test_names, factor))
    report: dict = {
        "git_commit": current_commit(),
        "interval_ratio": ratio,
        "train_regions": config["regions"]["names"],
        "reserved_regions": test_names,
    }
    for screen_name in settings["screens"]:
        rule = config["screens"][screen_name]
        train_rows = apply_screen(train, rule).reset_index(drop=True)
        test_rows = apply_screen(test, rule).reset_index(drop=True)
        table, folds = stack_train_test(train_rows, test_rows)
        predictions = all_predictions(table, config, folds, START_HEIGHT_EDGES)
        held = folds == 1
        y = table.loc[held, "mean_change"].to_numpy()
        blocks = assign_blocks(
            table.loc[held, "x"], table.loc[held, "y"], settings["block_size_m"]
        )
        entry = {"train_rows": len(train_rows), "test_rows": int(held.sum())}
        for label, pred in (
            ("as_trained_interval", {k: v[held] for k, v in predictions.items()}),
            (
                "stretched_to_2023",
                stretch_predictions(
                    {k: v[held] for k, v in predictions.items()}, ratio
                ),
            ),
        ):
            frame = pd.DataFrame(
                {
                    "y": y,
                    "block_id": blocks,
                    **{f"pred_{k}": v for k, v in pred.items()},
                }
            )
            entry[label] = {
                "overall": {k: score(y, v) for k, v in pred.items()},
                "contrasts": bootstrap_pairs(frame, config["bootstrap"], seed),
            }
        report[screen_name] = entry
        overall = entry["stretched_to_2023"]["overall"]
        print(
            f"{screen_name}: test rows {int(held.sum())} | MAE "
            + " ".join(
                f"{m} {overall[m]['mae']:.3f}"
                for m in (
                    "zero",
                    "eco_class_median",
                    "survey_height_x_eco_median",
                    "landsat_terrain_eco",
                )
            ),
            flush=True,
        )
    output = ensure_parent(project_root() / settings["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
