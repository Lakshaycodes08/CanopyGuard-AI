from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.forecasting.growth_contrasts import bootstrap_pairs
from canopyguard.forecasting.growth_model import all_predictions, score
from canopyguard.forecasting.region_transfer import (
    apply_screen,
    class_summary,
    far_from_other_regions,
    region_codes,
    stack_regions,
    utm_box,
)
from canopyguard.io import data_path, ensure_parent, project_root, with_region
from canopyguard.provenance import current_commit, file_sha256, write_provenance
from canopyguard.utils import set_seeds

START_HEIGHT_EDGES = [-1, 1, 5, 15, 30, 200]


def main() -> int:
    config = load_config("configs/growth.yaml")
    ingestion = load_config("configs/ingestion.yaml")
    crs = ingestion["landsat"]["grid_crs"]
    settings = config["regions"]
    seed = int(config["seed"])
    set_seeds(seed)
    names = settings["names"]
    regions = {name: load_region(name) for name in names}
    boxes = {name: utm_box(r["bbox"], crs) for name, r in regions.items()}
    base = data_path(config["table"]["output"])
    report: dict = {"git_commit": current_commit(), "seed": seed, "regions": names}
    for factor in settings["scales"]:
        tables = {}
        for name in names:
            path = with_region(base, regions[name]["suffix"])
            path = path.with_name(f"{path.stem}_x{factor}{path.suffix}")
            tables[name] = pd.read_parquet(path).dropna(subset=["mean_change"])
        stacked = stack_regions(tables).reset_index(drop=True)
        entry = report.setdefault(f"scale_x{factor}", {})
        for screen_name, rule in config["screens"].items():
            allowed = settings.get("screens_at_scale", {}).get(factor)
            if allowed is not None and screen_name not in allowed:
                continue
            table = apply_screen(stacked, rule).reset_index(drop=True)
            folds = region_codes(table, names)
            predictions = all_predictions(table, config, folds, START_HEIGHT_EDGES)
            scored = far_from_other_regions(table, boxes, float(settings["buffer_m"]))
            held_out = pd.DataFrame(
                {
                    "region": table["region"],
                    "y": table["mean_change"],
                    "easting": table["x"].to_numpy(),
                    "northing": table["y"].to_numpy(),
                    "canopy_share": table["canopy_share"].to_numpy(),
                    "p95_start": table["p95_start"].to_numpy(),
                    "loss_share": table["loss_share"].to_numpy(),
                    "scored": scored,
                    **{f"pred_{k}": v for k, v in predictions.items()},
                }
            )
            held_out["block_id"] = -1
            for name in names:
                rows = (table["region"] == name).to_numpy()
                held_out.loc[rows, "block_id"] = assign_blocks(
                    table.loc[rows, "x"], table.loc[rows, "y"], settings["block_size_m"]
                )
            output = ensure_parent(
                base.with_name(
                    f"growth_heldout_regions_{screen_name}_x{factor}{base.suffix}"
                )
            )
            held_out.to_parquet(output, index=False)
            write_provenance(
                output,
                source_url="local: region growth tables, leave-one-region-out",
                script_name="scripts/train_growth_regions.py",
                bbox_wgs84=regions["study"]["bbox"],
                crs=crs,
                row_count=len(held_out),
                config_sha256=file_sha256("configs/growth.yaml"),
            )
            section = entry.setdefault(screen_name, {})
            section["summary"] = class_summary(table, config)
            for name in names:
                rows = held_out[(held_out["region"] == name) & held_out["scored"]]
                y = rows["y"].to_numpy()
                section[name] = {
                    "scored_rows": len(rows),
                    "overall": {
                        k.removeprefix("pred_"): score(y, rows[k].to_numpy())
                        for k in rows.columns
                        if k.startswith("pred_")
                    },
                    "contrasts": bootstrap_pairs(rows, config["bootstrap"], seed),
                }
                skill = section[name]["overall"]
                print(
                    f"x{factor} {screen_name} held-out {name}: "
                    + " ".join(
                        f"{m} {skill[m]['mae']:.3f}"
                        for m in ("zero", "landsat", "landsat_site_eco")
                    ),
                    flush=True,
                )
    output = ensure_parent(project_root() / settings["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
