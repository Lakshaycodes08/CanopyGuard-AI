from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.forecasting.growth_model import (
    all_predictions,
    feature_columns,
    score,
    score_by_stratum,
    spatial_folds,
)
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import (
    current_commit,
    file_sha256,
    study_area_box,
    write_provenance,
)
from canopyguard.utils import set_seeds

START_HEIGHT_EDGES = [-1, 1, 5, 15, 30, 200]


def main() -> int:
    config = load_config("configs/growth.yaml")
    box = study_area_box(load_config("configs/study_area.yaml"))
    seed = int(config["seed"])
    set_seeds(seed)
    validation = config["validation"]
    target = config["model"]["target"]
    base = data_path(config["table"]["output"])
    report: dict = {"git_commit": current_commit(), "seed": seed, "target": target}
    for factor in config["table"]["scales"]:
        path = base.with_name(f"{base.stem}_x{factor}{base.suffix}")
        table = pd.read_parquet(path).dropna(subset=[target]).reset_index(drop=True)
        scale = report.setdefault(f"scale_x{factor}", {"rows": len(table)})
        scale["n_features"] = {
            name: len(feature_columns(table, prefixes))
            for name, prefixes in config["model"]["feature_sets"].items()
        }
        for size in validation["report_block_sizes_m"]:
            folds = spatial_folds(table, size, int(validation["folds"]), seed)
            predictions = all_predictions(table, config, folds, START_HEIGHT_EDGES)
            y = table[target].to_numpy()
            scale[f"block_{size}m"] = {
                "overall": {name: score(y, p) for name, p in predictions.items()},
                "by_start_height_m": score_by_stratum(
                    table, target, predictions, START_HEIGHT_EDGES
                ),
            }
            held_out = pd.DataFrame(
                {
                    "block_id": assign_blocks(table["x"], table["y"], size),
                    "fold": folds,
                    "y": y,
                    "easting": table["x"].to_numpy(),
                    "northing": table["y"].to_numpy(),
                    "p95_change": table["p95_change"].to_numpy(),
                    "p95_start": table["p95_start"].to_numpy(),
                    "canopy_share": table["canopy_share"].to_numpy(),
                    **{f"pred_{k}": v for k, v in predictions.items()},
                }
            )
            output = ensure_parent(
                base.with_name(f"growth_heldout_x{factor}_b{size}{base.suffix}")
            )
            held_out.to_parquet(output, index=False)
            write_provenance(
                output,
                source_url="local: growth table held-out predictions",
                script_name="scripts/train_growth_model.py",
                bbox_wgs84=box,
                crs="EPSG:32610",
                row_count=len(held_out),
                config_sha256=file_sha256("configs/growth.yaml"),
            )
            overall = scale[f"block_{size}m"]["overall"]
            print(
                f"x{factor} block {size} m: "
                + " ".join(
                    f"{name} {overall[name]['mae']:.3f}"
                    for name in ("zero", "landsat", "landsat_site_all")
                ),
                flush=True,
            )
    output = ensure_parent(project_root() / config["report"]["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
