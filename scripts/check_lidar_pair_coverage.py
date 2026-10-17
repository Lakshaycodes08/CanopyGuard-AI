from __future__ import annotations

import json

import numpy as np

from canopyguard.config import load_config
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.lidar import pair_coverage
from canopyguard.provenance import file_sha256, study_area_box, write_provenance
from canopyguard.viz.pair_coverage import save_map

SCRIPT = "scripts/check_lidar_pair_coverage.py"


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    lidar_config = load_config("configs/lidar.yaml")
    own = pair_coverage.settings(lidar_config)
    bbox = study_area_box(study_config)
    root = project_root()

    report, stats = pair_coverage.run(lidar_config, bbox)
    report_path = ensure_parent(root / own["report_json"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    arrays = {
        f"{epoch}_{field}": getattr(epoch_stats, field)
        for epoch, epoch_stats in stats.items()
        for field in ("point_count", "ground_count", "ground_sum", "surface_max")
    }
    stats_path = ensure_parent(data_path(own["tile_stats"]))
    np.savez_compressed(stats_path, **arrays)
    for path in (report_path, stats_path):
        write_provenance(
            path,
            source_url=own["fire_perimeter_url"],
            script_name=SCRIPT,
            bbox_wgs84=bbox,
            crs=study_config["study_area"]["crs"],
            config_sha256=file_sha256("configs/lidar.yaml"),
        )
    if report["tiles"]["candidates"]:
        save_map(report, bbox, root / own["figure"], dpi=100)
    print(json.dumps(report["answer"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
