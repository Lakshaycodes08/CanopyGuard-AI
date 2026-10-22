from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import planetary_computer
import pystac_client
from pyproj import Transformer

from canopyguard.config import load_config, load_region
from canopyguard.data.landsat_stac import (
    BAND_NAMES,
    assert_before_cutoff,
    collect_composites,
    season_window,
    study_grid,
)
from canopyguard.io import data_path, ensure_parent, with_region
from canopyguard.provenance import file_sha256, write_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="study")
    region = load_region(parser.parse_args().region)
    config = load_config("configs/ingestion.yaml")["landsat"]
    west, south, east, north = region["bbox"]
    to_utm = Transformer.from_crs("EPSG:4326", config["grid_crs"], always_xy=True)
    x0, y0 = to_utm.transform(west, south)
    x1, y1 = to_utm.transform(east, north)
    grid = study_grid((x0, y0, x1, y1), config)

    catalog = pystac_client.Client.open(
        config["stac_url"], modifier=planetary_computer.sign_inplace
    )
    cutoff = date.fromisoformat(config["cutoff"])
    years = list(range(int(config["first_year"]), cutoff.year + 1))
    composites, clear_counts, skipped = collect_composites(
        catalog,
        region["bbox"],
        grid,
        config,
        years,
        season_window,
        lambda dates: assert_before_cutoff(dates, cutoff),
    )

    left, top, width, height = grid
    output = ensure_parent(
        with_region(data_path(config["output_composites"]), region["suffix"])
    )
    np.savez_compressed(
        output,
        years=np.array(years),
        bands=np.array(BAND_NAMES),
        composites=composites,
        clear_counts=clear_counts,
        skipped_scenes=np.array(skipped, dtype=str),
        grid=np.array([left, top, config["grid_resolution_m"], width, height]),
        crs=config["grid_crs"],
        cutoff=config["cutoff"],
    )
    write_provenance(
        output,
        source_url=config["stac_url"],
        script_name="scripts/ingest_landsat.py",
        bbox_wgs84=region["bbox"],
        crs=config["grid_crs"],
        row_count=len(years),
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"Wrote {len(years)} summer composites to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
