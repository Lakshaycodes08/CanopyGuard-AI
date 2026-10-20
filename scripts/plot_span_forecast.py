from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.io import data_path, project_root, with_region
from canopyguard.risk.spans import cut_segments, project_lines
from canopyguard.viz.spans import forecast_figure


def main() -> int:
    cfg = load_config("configs/spans.yaml")
    ingestion = load_config("configs/ingestion.yaml")
    names = load_config("configs/growth.yaml")["regions"]["names"]
    crs = ingestion["landsat"]["grid_crs"]
    forecast = pd.read_parquet(data_path(cfg["forecast_table"]))
    segments = {}
    for name in names:
        region = load_region(name)
        path = with_region(
            data_path(ingestion["cec_lines"]["output"]), region["suffix"]
        )
        lines = project_lines(json.loads(path.read_text("utf-8")), crs)
        segments[name] = cut_segments(lines, float(cfg["segments"]["length_m"]))
    by_region = {n: forecast[forecast["region"] == n] for n in names}
    ranking = cfg["ranking"]
    jobs = [
        (
            "growth",
            ranking["growth"]["scores"]["landsat_terrain_eco"],
            ranking["growth"]["truth_column"],
            "Canopy growth along line segments, 2013 to 2022 (unburned canopy)",
            "Mean height change (m)",
            "Blues",
        ),
        (
            "loss",
            ranking["loss"]["scores"]["landsat_terrain_eco"],
            ranking["loss"]["truth_column"],
            "Canopy loss along line segments, 2013 to 2022 (any cause)",
            "Loss: predicted chance or observed share",
            "Oranges",
        ),
    ]
    out_dir = project_root() / "reports" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind, predicted, observed, title, unit, cmap in jobs:
        figure = forecast_figure(
            by_region, segments, predicted, observed, title, unit, cmap
        )
        path = out_dir / f"span_forecast_{kind}.png"
        figure.savefig(path, dpi=130)
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
