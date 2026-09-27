from __future__ import annotations

from canopyguard.config import load_config
from canopyguard.data.sentinel2 import (
    build_manifest,
    build_search_url,
    fetch_catalogue_items,
    write_manifest,
)
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    ingestion_config = load_config("configs/ingestion.yaml")
    source = ingestion_config["sentinel2"]
    search_url = build_search_url(study_config, ingestion_config)
    items = fetch_catalogue_items(search_url, source["request_timeout_seconds"])
    manifest = build_manifest(items, ingestion_config)
    output = write_manifest(manifest, source["output_manifest"])
    write_provenance(
        output,
        source_url=search_url,
        script_name="scripts/ingest_sentinel2.py",
        bbox_wgs84=study_area_box(study_config),
        crs=study_config["study_area"]["crs"],
        row_count=manifest["item_count"],
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"Wrote {manifest['item_count']} Sentinel-2 items to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
