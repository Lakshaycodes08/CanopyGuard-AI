from __future__ import annotations

import json

import numpy as np
import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.forecasting.region_transfer import apply_screen
from canopyguard.forecasting.screen_check import agreement, drop_auc, kept_and_removed
from canopyguard.io import data_path, ensure_parent, project_root, with_region
from canopyguard.provenance import current_commit


def keep_mask(table: pd.DataFrame, rule: dict) -> np.ndarray:
    return table.index.isin(apply_screen(table, rule).index)


def main() -> int:
    config = load_config("configs/growth.yaml")
    settings = config["satellite_screen"]
    threshold = float(settings["echosat_row_threshold"])
    base = data_path(config["table"]["output"])
    report: dict = {"git_commit": current_commit()}
    for name in config["regions"]["names"]:
        path = with_region(base, load_region(name)["suffix"])
        path = path.with_name(f"{path.stem}_x3{path.suffix}")
        table = pd.read_parquet(path).dropna(subset=["mean_change"])
        table = table.reset_index(drop=True)
        lidar_keep = keep_mask(table, config["screens"]["undisturbed"])
        sat_keep = keep_mask(table, config["screens"]["undisturbed_satellite"])
        fire_free = (table["burned"] <= 0).to_numpy()
        lidar_loss = (table["loss_share"] > 0.1).to_numpy()
        entry = {
            "rows": len(table),
            "kept_share": {
                "lidar_screen": float(lidar_keep.mean()),
                "satellite_screen": float(sat_keep.mean()),
                "both": float((lidar_keep & sat_keep).mean()),
            },
            "echosat_vs_lidar_screen": kept_and_removed(table, lidar_keep, threshold),
            "echosat_vs_satellite_screen": kept_and_removed(table, sat_keep, threshold),
            "echosat_vs_fire_free_only": kept_and_removed(table, fire_free, threshold),
            "satellite_flag_vs_lidar_loss": agreement(
                ~sat_keep & fire_free, lidar_loss
            ),
            "nbr_drop_auc_for_lidar_loss": drop_auc(table, lidar_loss),
        }
        report[name] = entry
        sat = entry["echosat_vs_satellite_screen"]
        lid = entry["echosat_vs_lidar_screen"]
        print(
            f"{name}: kept lidar {entry['kept_share']['lidar_screen']:.2f} "
            f"sat {entry['kept_share']['satellite_screen']:.2f} | ECHOSAT abrupt-loss "
            f"rate in kept rows: lidar {lid['kept']['echosat_abrupt_loss_rows']:.3f} "
            f"sat {sat['kept']['echosat_abrupt_loss_rows']:.3f}; removed: "
            f"lidar {lid['removed']['echosat_abrupt_loss_rows']:.3f} "
            f"sat {sat['removed']['echosat_abrupt_loss_rows']:.3f} | "
            f"NBR-drop AUC {entry['nbr_drop_auc_for_lidar_loss']:.3f}",
            flush=True,
        )
    output = ensure_parent(project_root() / settings["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
