from __future__ import annotations

import argparse

import numpy as np

from canopyguard.config import load_config, load_region
from canopyguard.data.gap_landfire import ecosystem_rasters
from canopyguard.data.sonoma_veg import class_rasters, fetch_class_polygons
from canopyguard.data.terraclimate import climate_normals, sample_on_grid
from canopyguard.data.terrain_stac import elevation_on_grid
from canopyguard.features.terrain import terrain_features
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def save(rasters, path, source_url, script, box, crs, suffix):
    output = ensure_parent(with_region(data_path(path), suffix))
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    suffix = region["suffix"]
    box = region["bbox"]
    crs = landsat["grid_crs"]
    composites = np.load(with_region(data_path(landsat["output_composites"]), suffix))
    left, top, step, width, height = composites["grid"]
    grid = (float(left), float(top), float(step), int(width), int(height))
    script = "scripts/ingest_site_sources.py"

    dem = ingestion["nasadem"]
    elevation = elevation_on_grid(grid, box, landsat["stac_url"], crs, dem)
    layers = terrain_features(elevation, step, int(dem["tpi_radius_pixels"]))
    save(layers, dem["output"], landsat["stac_url"], script, box, crs, suffix)

    tc = ingestion["terraclimate"]
    normals = climate_normals(box, landsat["stac_url"], tc)
    save(
        sample_on_grid(normals, grid, crs),
        tc["output"],
        landsat["stac_url"],
        script,
        box,
        crs,
        suffix,
    )

    gap = ingestion["gap_ecosystems"]
    ecosystems = ecosystem_rasters(grid, box, landsat["stac_url"], crs, gap)
    save(ecosystems, gap["output"], landsat["stac_url"], script, box, crs, suffix)

    veg = ingestion["sonoma_veg"]
    polygons = fetch_class_polygons(box, crs, veg)
    print(f"{len(polygons)} vegetation polygons", flush=True)
    save(
        class_rasters(polygons, grid, veg),
        veg["output"],
        veg["url"],
        script,
        box,
        crs,
        suffix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
