from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config
from canopyguard.forecasting.growth_model import (
    feature_columns,
    out_of_fold_predictions,
    score,
    score_by_stratum,
    spatial_folds,
)
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import current_commit
from canopyguard.utils import set_seeds

START_HEIGHT_EDGES = [-1, 1, 5, 15, 30, 200]


def main() -> int:
    config = load_config("configs/growth.yaml")
    seed = int(config["seed"])
    set_seeds(seed)
    validation = config["validation"]
    target = config["model"]["target"]
    params = config["model"]["lightgbm"]
    base = data_path(config["table"]["output"])
    report: dict = {"git_commit": current_commit(), "seed": seed, "target": target}
    for factor in config["table"]["scales"]:
        path = base.with_name(f"{base.stem}_x{factor}{base.suffix}")
        table = pd.read_parquet(path).dropna(subset=[target]).reset_index(drop=True)
        columns = feature_columns(table)
        scale = report.setdefault(f"scale_x{factor}", {"rows": len(table)})
        for block_size in validation["report_block_sizes_m"]:
            folds = spatial_folds(table, block_size, int(validation["folds"]), seed)
            pred = out_of_fold_predictions(table, columns, target, folds, params, seed)
            y = table[target].to_numpy()
            scale[f"block_{block_size}m"] = {
                "overall": {name: score(y, p) for name, p in pred.items()},
                "by_start_height_m": score_by_stratum(
                    table, target, pred, START_HEIGHT_EDGES
                ),
            }
            skill = scale[f"block_{block_size}m"]["overall"]
            print(
                f"x{factor} block {block_size} m: "
                f"model MAE {skill['model']['mae']:.3f} "
                f"mean {skill['train_mean']['mae']:.3f} "
                f"zero {skill['zero']['mae']:.3f}  "
                f"R2 {skill['model']['r2']:.3f}",
                flush=True,
            )
    output = ensure_parent(project_root() / config["report"]["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
