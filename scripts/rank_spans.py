from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import current_commit
from canopyguard.risk.spans import (
    assign_pixels,
    cut_segments,
    evaluate_ranking,
    half_width_label,
    project_lines,
    segment_scores,
)
from canopyguard.utils import set_seeds


def main() -> int:
    config = load_config("configs/spans.yaml")
    growth = load_config("configs/growth.yaml")
    ingestion = load_config("configs/ingestion.yaml")
    seed = int(config["seed"])
    set_seeds(seed)
    crs = ingestion["landsat"]["grid_crs"]
    lines_file = data_path(ingestion["cec_lines"]["output"])
    lines = project_lines(json.loads(lines_file.read_text("utf-8")), crs)
    segments = cut_segments(lines, float(config["segments"]["length_m"]))
    base = data_path(growth["table"]["output"])
    ranking = config["ranking"]
    report: dict = {
        "git_commit": current_commit(),
        "note": "Research prioritisation only; not a clearance determination.",
        "line_segments": len(segments),
    }
    for size in ranking["heldout_block_sizes_m"]:
        path = base.with_name(
            f"growth_heldout_x{ranking['scale']}_b{size}{base.suffix}"
        )
        pixels = pd.read_parquet(path)
        pred_columns = [c for c in pixels.columns if c.startswith("pred_")]
        for half_width in config["corridor"]["half_widths_m"]:
            assigned = assign_pixels(
                pixels["easting"].to_numpy(),
                pixels["northing"].to_numpy(),
                segments,
                float(half_width),
            )
            table = segment_scores(
                pixels, assigned, segments, pred_columns, config["truth"]
            )
            table["block"] = assign_blocks(table["easting"], table["northing"], size)
            entry = report.setdefault(f"block_{size}m", {}).setdefault(
                f"half_width_{half_width_label(half_width)}", {}
            )
            for truth in ("truth_mean_change", "truth_p95_change"):
                entry[truth] = evaluate_ranking(table, truth, config, seed)
            headline = entry["truth_mean_change"]
            print(
                f"block {size} m, half width {half_width} m: "
                f"{headline['segments']} segments",
                flush=True,
            )
    output = ensure_parent(project_root() / config["output"])
    output.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
