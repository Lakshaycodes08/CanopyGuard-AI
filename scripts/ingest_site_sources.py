from __future__ import annotations

import numpy as np

from canopyguard.config import load_config
from canopyguard.data.gap_landfire import ecosystem_rasters
from canopyguard.data.sonoma_veg import class_rasters, fetch_class_polygons
from canopyguard.data.terraclimate import climate_normals, sample_on_grid
from canopyguard.data.terrain_stac import elevation_on_grid
from canopyguard.features.terrain import terrain_features
from canopyguard.io import data_path, ensure_parent
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def save(rasters, path, source_url, script, box, crs):
    output = ensure_parent(data_path(path))
    np.savez_compressed(output, **rasters)
    write_provenance(
        output,
        source_url=source_url,
        script_name=script,
        bbox_wgs84=box,
        crs=crs,
        row_count=len(rasters),
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"{len(rasters)} layers -> {output}", flush=True)


def main() -> int:
    ingestion = load_config("configs/ingestion.yaml")
    landsat = ingestion["landsat"]
    box = study_area_box(load_config("configs/study_area.yaml"))
    crs = landsat["grid_crs"]
    composites = np.load(data_path(landsat["output_composites"]))
    left, top, step, width, height = composites["grid"]
    grid = (float(left), float(top), float(step), int(width), int(height))
    script = "scripts/ingest_site_sources.py"

    dem = ingestion["nasadem"]
    elevation = elevation_on_grid(grid, box, landsat["stac_url"], crs, dem)
    layers = terrain_features(elevation, step, int(dem["tpi_radius_pixels"]))
    save(layers, dem["output"], landsat["stac_url"], script, box, crs)

    tc = ingestion["terraclimate"]
    normals = climate_normals(box, landsat["stac_url"], tc)
    save(
        sample_on_grid(normals, grid, crs),
        tc["output"],
        landsat["stac_url"],
        script,
        box,
        crs,
    )

    gap = ingestion["gap_ecosystems"]
    ecosystems = ecosystem_rasters(grid, box, landsat["stac_url"], crs, gap)
    save(ecosystems, gap["output"], landsat["stac_url"], script, box, crs)

    veg = ingestion["sonoma_veg"]
    polygons = fetch_class_polygons(box, crs, veg)
    print(f"{len(polygons)} vegetation polygons", flush=True)
    save(
        class_rasters(polygons, grid, veg), veg["output"], veg["url"], script, box, crs
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
