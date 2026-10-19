from __future__ import annotations

import numpy as np

from canopyguard.config import load_config
from canopyguard.features.landsat_history import history_features
from canopyguard.forecasting.growth_table import labels_on_pixel_grid, table_at_scale
from canopyguard.io import data_path, ensure_parent
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def main() -> int:
    config = load_config("configs/growth.yaml")
    study_box = study_area_box(load_config("configs/study_area.yaml"))
    composites = np.load(data_path(config["features"]["composites"]))
    left, top, step, width, height = composites["grid"]
    grid = (float(left), float(top), float(step), int(width), int(height))
    features = history_features(
        composites["composites"], composites["years"], config["features"]
    )
    labels = np.load(data_path(config["labels"]["archive"]))
    pixels = labels_on_pixel_grid(
        {name: labels[name] for name in labels.files},
        grid,
        int(config["labels"]["min_label_cells_per_pixel"]),
    )
    share = float(config["features"]["min_valid_pixel_share"])
    output = ensure_parent(data_path(config["table"]["output"]))
    for factor in config["table"]["scales"]:
        table = table_at_scale(pixels, features, int(factor), grid, share)
        table["scale_pixels"] = int(factor)
        path = output.with_name(f"{output.stem}_x{factor}{output.suffix}")
        table.to_parquet(path, index=False)
        write_provenance(
            path,
            source_url="local: landsat composites + LiDAR label archive",
            script_name="scripts/build_growth_table.py",
            bbox_wgs84=study_box,
            crs="EPSG:32610",
            row_count=len(table),
            config_sha256=file_sha256("configs/growth.yaml"),
        )
        print(f"scale x{factor}: {len(table):,} rows -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
