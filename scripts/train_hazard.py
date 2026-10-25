from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.forecasting.growth_model import (
    columns_with_survey,
    dominant_class,
    feature_columns,
)
from canopyguard.forecasting.hazard_model import (
    auc_roc,
    disturbance_labels,
    group_rate,
    held_out_probability,
    ranking_scores,
)
from canopyguard.forecasting.region_transfer import (
    far_from_other_regions,
    load_region_tables,
    region_codes,
    stack_regions,
    utm_box,
)
from canopyguard.io import data_path, ensure_parent, project_root, with_region
from canopyguard.provenance import current_commit, file_sha256, write_provenance
from canopyguard.risk.spans import block_bootstrap_interval
from canopyguard.utils import set_seeds


def auc_difference(first, second, label):
    """Statistic of row indices: AUC of `first` minus AUC of `second`."""

    def difference(indices):
        return auc_roc(first[indices], label[indices]) - auc_roc(
            second[indices], label[indices]
        )

    return difference


def main() -> int:
    config = load_config("configs/growth.yaml")
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=None)
    args = parser.parse_args()
    settings = dict(config["hazard"])
    default_scale = int(settings["scale"])
    settings["scale"] = args.scale or default_scale
    suffix = "" if settings["scale"] == default_scale else f"_x{settings['scale']}"
    seed = int(config["seed"])
    set_seeds(seed)
    crs = load_config("configs/ingestion.yaml")["landsat"]["grid_crs"]
    names = config["regions"]["names"]
    regions = {n: load_region(n) for n in names}
    boxes = {n: utm_box(r["bbox"], crs) for n, r in regions.items()}
    base = data_path(config["table"]["output"])
    tables = load_region_tables(config, names, int(settings["scale"]), crs)
    table = stack_regions(tables).reset_index(drop=True)
    folds = region_codes(table, names)
    scored = far_from_other_regions(table, boxes, float(config["regions"]["buffer_m"]))
    block = np.zeros(len(table), dtype=np.int64)
    for name in names:
        rows = (table["region"] == name).to_numpy()
        block[rows] = assign_blocks(
            table.loc[rows, "x"],
            table.loc[rows, "y"],
            config["regions"]["block_size_m"],
        )
    eco = pd.Series(dominant_class(table), index=table.index)
    params = config["model"]["lightgbm"]
    k_fractions = list(settings["k_fractions"])
    report: dict = {"git_commit": current_commit(), "seed": seed}
    held_out = pd.DataFrame(
        {
            "region": table["region"],
            "easting": table["x"],
            "northing": table["y"],
            "canopy_share": table["canopy_share"],
            "p95_start": table["p95_start"],
            "scored": scored,
        }
    )
    for label_name, label in disturbance_labels(table, settings["labels"]).items():
        scores = {
            "eco_class_rate": group_rate(eco, label, folds),
            **{
                n: held_out_probability(
                    table,
                    feature_columns(table, config["model"]["feature_sets"][n]),
                    label,
                    folds,
                    params,
                    seed,
                )
                for n in settings["feature_sets"]
            },
            "satellite_plus_survey_height": held_out_probability(
                table, columns_with_survey(table, config), label, folds, params, seed
            ),
        }
        held_out[f"label_{label_name}"] = label
        for model, score in scores.items():
            held_out[f"prob_{label_name}_{model}"] = score
        entry = report.setdefault(label_name, {})
        for name in names:
            rows = (table["region"] == name).to_numpy() & scored
            region_entry = entry.setdefault(name, {"scored_rows": int(rows.sum())})
            for model, score in scores.items():
                region_entry[model] = ranking_scores(
                    score[rows], label[rows], k_fractions
                )
            low, high = block_bootstrap_interval(
                auc_difference(
                    scores["landsat_terrain_eco"][rows],
                    scores["eco_class_rate"][rows],
                    label[rows],
                ),
                block[rows],
                int(settings["bootstrap_resamples"]),
                float(settings["confidence_level"]),
                seed,
            )
            region_entry["auc_gain_over_eco_class_rate"] = {
                "difference": region_entry["landsat_terrain_eco"]["auc"]
                - region_entry["eco_class_rate"]["auc"],
                "ci_low": low,
                "ci_high": high,
            }
            print(
                f"{label_name} held-out {name} (base rate "
                f"{region_entry['eco_class_rate']['base_rate']:.2f}): AUC "
                + " ".join(
                    f"{m} {region_entry[m]['auc']:.3f}"
                    for m in ("eco_class_rate", "landsat", "landsat_terrain_eco")
                ),
                flush=True,
            )
    held_path = ensure_parent(
        base.with_name(f"hazard_heldout_x{settings['scale']}{base.suffix}")
    )
    held_out.to_parquet(held_path, index=False)
    write_provenance(
        held_path,
        source_url="local: region growth tables, leave-one-region-out",
        script_name="scripts/train_hazard.py",
        bbox_wgs84=regions["study"]["bbox"],
        crs=crs,
        row_count=len(held_out),
        config_sha256=file_sha256("configs/growth.yaml"),
    )
    output = ensure_parent(with_region(project_root() / settings["output"], suffix))
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
