from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import rasterio

from canopyguard.config import load_config
from canopyguard.data import echosat, echosat_fire
from canopyguard.io import data_path, ensure_parent, project_root
from canopyguard.provenance import file_sha256, study_area_box, write_provenance
from canopyguard.viz.echosat import save_sample_figure

SCRIPT = "scripts/check_echosat.py"


def _check(source: dict[str, Any], bbox: tuple[float, ...]):
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
    perimeter = echosat_fire.fetch_fire_perimeter(
        source["fire_check"], bbox, source["request_timeout_seconds"]
    )
    report["fire_check"] = echosat_fire.fire_check(box, perimeter, source)
    return report, box, copy, nodata


def _record(path: Path, source_url: str, bbox, crs: str) -> None:
    write_provenance(
        path,
        source_url=source_url,
        script_name=SCRIPT,
        bbox_wgs84=bbox,
        crs=crs,
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    source = load_config("configs/ingestion.yaml")["echosat"]
    bbox = study_area_box(study_config)
    root = project_root()

    report, box, copy, nodata = _check(source, bbox)
    report_path = ensure_parent(root / source["coverage_report"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _record(copy, source["tile_url"], bbox, report["raster_crs"])
    _record(report_path, source["tile_url"], bbox, study_config["study_area"]["crs"])
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
    check = report["fire_check"]
    print(f"Fire peak step {check['peak_step']}, expected {check['expected_step']}")
    print(f"Wrote {copy}, {report_path}, {figure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
