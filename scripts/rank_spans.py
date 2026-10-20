from __future__ import annotations

import json

import pandas as pd

from canopyguard.config import load_config, load_region
from canopyguard.evaluation.blocks import assign_blocks
from canopyguard.io import data_path, ensure_parent, project_root, with_region
from canopyguard.provenance import current_commit, file_sha256, write_provenance
from canopyguard.risk.spans import (
    assign_pixels,
    cut_segments,
    evaluate_ranking,
    project_lines,
    segment_table,
)
from canopyguard.utils import set_seeds


def corridor_table(
    pixels: pd.DataFrame,
    segments: pd.DataFrame,
    half_width: float,
    spec: dict,
    cfg: dict,
) -> pd.DataFrame:
    """Segment means of the truth and every score over canopy pixels."""
    pixels = pixels[
        pixels["scored"] & (pixels["canopy_share"] >= cfg["truth"]["min_canopy_share"])
    ]
    columns = sorted({spec["truth_column"], *spec["scores"].values()})
    assigned = assign_pixels(
        pixels["easting"].to_numpy(),
        pixels["northing"].to_numpy(),
        segments,
        half_width,
    )
    table = segment_table(
        pixels, assigned, segments, columns, int(cfg["truth"]["min_pixels_per_segment"])
    )
    table["block"] = assign_blocks(
        table["easting"], table["northing"], cfg["ranking"]["block_size_m"]
    )
    return table


def main() -> int:
    cfg = load_config("configs/spans.yaml")
    growth_cfg = load_config("configs/growth.yaml")
    ingestion = load_config("configs/ingestion.yaml")
    seed = int(cfg["seed"])
    set_seeds(seed)
    crs = ingestion["landsat"]["grid_crs"]
    names = growth_cfg["regions"]["names"]
    processed = data_path(growth_cfg["table"]["output"]).parent
    ranking = cfg["ranking"]
    heldout = {
        kind: pd.read_parquet(processed / ranking[kind]["heldout"])
        for kind in ("growth", "loss")
    }
    report: dict = {
        "git_commit": current_commit(),
        "note": "Research prioritisation only; not a clearance determination.",
    }
    for half_width in cfg["corridor"]["half_widths_m"]:
        key = f"half_width_{int(half_width)}m"
        pooled: dict[str, list[pd.DataFrame]] = {"growth": [], "loss": []}
        for name in names:
            region = load_region(name)
            lines_file = with_region(
                data_path(ingestion["cec_lines"]["output"]), region["suffix"]
            )
            lines = project_lines(json.loads(lines_file.read_text("utf-8")), crs)
            segments = cut_segments(lines, float(cfg["segments"]["length_m"]))
            for kind in ("growth", "loss"):
                spec = ranking[kind]
                pixels = heldout[kind][heldout[kind]["region"] == name]
                table = corridor_table(pixels, segments, float(half_width), spec, cfg)
                table["region"] = name
                pooled[kind].append(table)
                result = evaluate_ranking(
                    table,
                    spec["truth_column"],
                    spec["scores"],
                    spec["headline"],
                    spec["contrasts"],
                    cfg,
                    seed,
                )
                report.setdefault(key, {}).setdefault(kind, {})[name] = result
        for kind in ("growth", "loss"):
            spec = ranking[kind]
            tables = []
            for offset, table in enumerate(pooled[kind]):
                shifted = table.copy()
                shifted["block"] = shifted["block"] + offset * 10_000_000
                tables.append(shifted)
            combined = pd.concat(tables, ignore_index=True)
            report[key][kind]["pooled"] = evaluate_ranking(
                combined,
                spec["truth_column"],
                spec["scores"],
                spec["headline"],
                spec["contrasts"],
                cfg,
                seed,
            )
            pooled_result = report[key][kind]["pooled"]
            head = pooled_result["scores"][spec["headline"]]["recall_at_20pct"]
            chance = pooled_result["scores"]["random"]["recall_at_20pct"]
            print(
                f"{key} {kind}: {pooled_result['segments']} segments, "
                f"headline recall@20% {head:.2f}, random {chance:.2f}",
                flush=True,
            )
        if int(half_width) == int(cfg["corridor"]["primary_half_width_m"]):
            frames = []
            for growth, loss in zip(pooled["growth"], pooled["loss"], strict=True):
                merged = growth.join(
                    loss, how="outer", lsuffix="_growth", rsuffix="_loss"
                )
                merged["region"] = growth["region"].combine_first(loss["region"])
                frames.append(merged)
            output = ensure_parent(data_path(cfg["forecast_table"]))
            pd.concat(frames).to_parquet(output)
            write_provenance(
                output,
                source_url="local: region held-out predictions and CEC line segments",
                script_name="scripts/rank_spans.py",
                bbox_wgs84=load_region("study")["bbox"],
                crs=crs,
                row_count=int(sum(len(f) for f in frames)),
                config_sha256=file_sha256("configs/spans.yaml"),
            )
    out = ensure_parent(project_root() / cfg["output"])
    out.write_text(json.dumps(report, indent=2, default=float) + "\n", "utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
