from __future__ import annotations

from canopyguard.config import load_config
from canopyguard.data.sentinel2 import (
    build_manifest,
    build_search_url,
    fetch_catalogue_items,
    write_manifest,
)


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    ingestion_config = load_config("configs/ingestion.yaml")
    source = ingestion_config["sentinel2"]
    search_url = build_search_url(study_config, ingestion_config)
    items = fetch_catalogue_items(search_url, source["request_timeout_seconds"])
    manifest = build_manifest(items, ingestion_config)
    output = write_manifest(manifest, source["output_manifest"])
    print(f"Wrote {manifest['item_count']} Sentinel-2 items to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
