from __future__ import annotations

import argparse

from canopyguard.config import load_config
from canopyguard.data.lidar_fetch import (
    build_catalog_url,
    probe_coverage,
)
from canopyguard.io import data_path, ensure_parent
from canopyguard.lidar.footprint import as_box, covered_area_km2, probe_grid
from canopyguard.provenance import write_provenance


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe LiDAR coverage for an epoch.")
    parser.add_argument("identifier", help="Catalogue dataset identifier.")
    parser.add_argument("--rows", type=int, default=6)
    parser.add_argument("--columns", type=int, default=3)
    args = parser.parse_args()

    study = load_config("configs/study_area.yaml")["study_area"]["bbox"]
    box = as_box(study["west"], study["south"], study["east"], study["north"])
    probes = probe_grid(box, args.rows, args.columns)
    present = probe_coverage(probes, args.identifier)

    output = ensure_parent(
        data_path("interim", "lidar", f"{args.identifier}.coverage.json")
    )
    output.write_text(_report(args.identifier, probes, present, box), encoding="utf-8")
    write_provenance(
        output,
        source_url=build_catalog_url(box),
        script_name="scripts/fetch_lidar.py",
        bbox_wgs84=(study["west"], study["south"], study["east"], study["north"]),
        crs="EPSG:4326",
        row_count=len(probes),
    )
    print(f"Covered {covered_area_km2(probes, present):.1f} km2, wrote {output}")
    return 0


def _report(identifier, probes, present, box) -> str:
    import json

    return json.dumps(
        {
            "identifier": identifier,
            "source": build_catalog_url(box),
            "covered_km2": covered_area_km2(probes, present),
            "probes": [
                {"box": list(probe), "present": found}
                for probe, found in zip(probes, present, strict=True)
            ],
        },
        indent=2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
