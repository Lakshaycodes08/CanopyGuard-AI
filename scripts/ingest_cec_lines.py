from __future__ import annotations

import json

from canopyguard.config import load_config
from canopyguard.data.cec_lines import fetch_lines
from canopyguard.io import data_path, ensure_parent
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def main() -> int:
    config = load_config("configs/ingestion.yaml")["cec_lines"]
    box = study_area_box(load_config("configs/study_area.yaml"))
    lines = fetch_lines(box, config)
    output = ensure_parent(data_path(config["output"]))
    output.write_text(json.dumps(lines) + "\n", "utf-8")
    write_provenance(
        output,
        source_url=config["url"],
        script_name="scripts/ingest_cec_lines.py",
        bbox_wgs84=box,
        crs="EPSG:4326",
        row_count=len(lines["features"]),
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"Wrote {len(lines['features'])} line features to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
