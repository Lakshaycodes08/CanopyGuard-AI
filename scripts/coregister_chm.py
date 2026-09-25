from __future__ import annotations

import argparse
import json

from canopyguard.config import load_config
from canopyguard.io import data_path, ensure_parent
from canopyguard.lidar.coreg import accept, align, apply_horizontal_shift
from canopyguard.lidar.gridio import read_grid, write_grid
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser(description="Co-register one tile pair.")
    parser.add_argument("reference_dtm")
    parser.add_argument("moving_dtm")
    parser.add_argument("moving_chm")
    parser.add_argument("output_chm")
    args = parser.parse_args()

    settings = load_config("configs/lidar.yaml")["coregistration"]
    resolution = load_config("configs/lidar.yaml")["chm"]["resolution_m"]

    reference, _ = read_grid(args.reference_dtm)
    moving, _ = read_grid(args.moving_dtm)
    shift = align(
        reference,
        moving,
        resolution,
        settings["min_slope_deg"],
        settings["max_slope_deg"],
        settings["max_iterations"],
        settings["convergence_tolerance_m"],
    )
    shift["accepted"] = float(accept(shift, settings["max_accepted_shift_m"]))

    canopy, profile = read_grid(args.moving_chm)
    write_grid(
        args.output_chm, apply_horizontal_shift(canopy, shift, resolution), profile
    )

    study_config = load_config("configs/study_area.yaml")
    box = study_area_box(study_config)
    crs = study_config["study_area"]["crs"]
    config_sha256 = file_sha256("configs/lidar.yaml")
    write_provenance(
        args.output_chm,
        source_url=f"local:{args.moving_chm}",
        script_name="scripts/coregister_chm.py",
        bbox_wgs84=box,
        crs=crs,
        config_sha256=config_sha256,
    )

    report = ensure_parent(data_path("processed", "truth", "coregistration.jsonl"))
    with report.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"moving": args.moving_chm, **shift}) + "\n")
    write_provenance(
        report,
        source_url=f"local:{args.moving_dtm}",
        script_name="scripts/coregister_chm.py",
        bbox_wgs84=box,
        crs=crs,
        config_sha256=config_sha256,
    )
    print(json.dumps(shift, indent=2))
    return 0 if shift["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
