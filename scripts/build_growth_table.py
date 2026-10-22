from __future__ import annotations

import argparse
import json
from datetime import date

import numpy as np

from canopyguard.config import load_config, load_region
from canopyguard.data.echosat_drop import expand_percent
from canopyguard.features.disturbance import nbr_drop, satellite_disturbed
from canopyguard.features.fire import burned_raster, perimeters_in_window
from canopyguard.features.landsat_history import history_features
from canopyguard.forecasting.growth_table import labels_on_pixel_grid, table_at_scale
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def load_echosat_drop(ingestion: dict, screen: dict, suffix: str, shape: tuple):
    """Full-resolution drop share, else the compact copy, else an empty raster."""
    full = with_region(data_path(screen["echosat_drop"]), suffix)
    if full.exists():
        return np.load(full)["echosat_drop_share"]
    compact = with_region(
        data_path(ingestion["echosat_drop"]["compact_output"]), suffix
    )
    if compact.exists():
        saved = np.load(compact)
        return expand_percent(saved["percent"], int(saved["factor"]), shape)
    return np.full(shape, np.nan, dtype=np.float32)


def main() -> int:
    config = load_config("configs/growth.yaml")
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    suffix = region["suffix"]
    composites = np.load(
        with_region(data_path(config["features"]["composites"]), suffix)
    )
    left, top, step, width, height = composites["grid"]
    grid = (float(left), float(top), float(step), int(width), int(height))
    features = history_features(
        composites["composites"], composites["years"], config["features"]
    )
    for source in config["features"]["static_sources"]:
        layers = np.load(with_region(data_path(source), suffix))
        features.update({name: layers[name] for name in layers.files})
    epochs = {e["name"]: e for e in load_config("configs/lidar.yaml")["epochs"]}
    first, last = config["features"]["fire_window_epochs"]
    perimeters = json.loads(
        with_region(data_path(config["features"]["fire_perimeters"]), suffix).read_text(
            "utf-8"
        )
    )
    features["burned"] = burned_raster(
        perimeters_in_window(
            perimeters,
            date.fromisoformat(epochs[first]["end"]),
            date.fromisoformat(epochs[last]["start"]),
        ),
        grid,
        composites["crs"].item(),
    )
    ingestion = load_config("configs/ingestion.yaml")
    screen = config["satellite_screen"]
    post = np.load(with_region(data_path(screen["post_composites"]), suffix))
    drops = nbr_drop(composites["composites"], post["composites"], screen)
    features.update(drops)
    features["sat_disturbed"] = satellite_disturbed(
        drops["sat_nbr_drop_final"], float(screen["threshold"])
    )
    # ECHOSAT is a cross-check only; without its files the column stays empty.
    features["echosat_drop_share"] = load_echosat_drop(
        ingestion, screen, suffix, (int(height), int(width))
    )
    labels = np.load(with_region(data_path(config["labels"]["archive"]), suffix))
    pixels = labels_on_pixel_grid(
        {name: labels[name] for name in labels.files},
        grid,
        int(config["labels"]["min_label_cells_per_pixel"]),
    )
    share = float(config["features"]["min_valid_pixel_share"])
    output = ensure_parent(with_region(data_path(config["table"]["output"]), suffix))
    for factor in config["table"]["scales"]:
        table = table_at_scale(pixels, features, int(factor), grid, share)
        table["scale_pixels"] = int(factor)
        path = output.with_name(f"{output.stem}_x{factor}{output.suffix}")
        table.to_parquet(path, index=False)
        write_provenance(
            path,
            source_url="local: landsat composites + LiDAR label archive",
            script_name="scripts/build_growth_table.py",
            bbox_wgs84=region["bbox"],
            crs="EPSG:32610",
            row_count=len(table),
            config_sha256=file_sha256("configs/growth.yaml"),
        )
        print(f"scale x{factor}: {len(table):,} rows -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
