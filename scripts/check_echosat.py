from __future__ import annotations

import json

import rasterio

from canopyguard.config import load_config
from canopyguard.data import echosat
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import file_sha256, study_area_box, write_provenance
from canopyguard.viz.echosat import save_sample_figure


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    source = load_config("configs/ingestion.yaml")["echosat"]
    bbox = study_area_box(study_config)
    root = project_root()

    with echosat.open_environment(source):
        metadata = echosat.remote_metadata(
            source["tile_url"], source["request_timeout_seconds"]
        )
        with rasterio.open(f"/vsicurl/{source['tile_url']}") as src:
            echosat.validate_raster(src, source)
            box = echosat.read_box(src, bbox)
            report = echosat.build_report(src, box, source)
            report["remote_file"] = metadata
            copy = echosat.write_box_copy(src, box, data_path(source["box_copy"]))
            nodata = src.nodata

    report_path = ensure_parent(root / source["coverage_report"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for path, crs in (
        (copy, report["raster_crs"]),
        (report_path, study_config["study_area"]["crs"]),
    ):
        write_provenance(
            path,
            source_url=source["tile_url"],
            script_name="scripts/check_echosat.py",
            bbox_wgs84=bbox,
            crs=crs,
            config_sha256=file_sha256("configs/ingestion.yaml"),
        )
    figure = save_sample_figure(
        box.data,
        box.inside,
        source["band_years"],
        source["check_years"],
        nodata,
        source["figure"],
        source["height_scale_to_m"],
        root / source["sample_figure"],
    )
    for row in report["per_year"]:
        print(f"{row['year']}: {row['valid_pixels']} valid of {row['box_pixels']}")
    print(f"Wrote {copy}, {report_path}, {figure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
