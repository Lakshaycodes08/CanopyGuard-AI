from __future__ import annotations

import warnings
from datetime import date

import numpy as np
import planetary_computer
import pystac_client
from pyproj import Transformer

from canopyguard.config import load_config
from canopyguard.data.landsat_stac import (
    BAND_NAMES,
    assert_before_cutoff,
    season_window,
    study_grid,
    year_composite,
)
from canopyguard.io import data_path, ensure_parent
from canopyguard.provenance import file_sha256, study_area_box, write_provenance


def main() -> int:
    study_config = load_config("configs/study_area.yaml")
    config = load_config("configs/ingestion.yaml")["landsat"]
    west, south, east, north = study_area_box(study_config)
    to_utm = Transformer.from_crs("EPSG:4326", config["grid_crs"], always_xy=True)
    x0, y0 = to_utm.transform(west, south)
    x1, y1 = to_utm.transform(east, north)
    grid = study_grid((x0, y0, x1, y1), config)

    catalog = pystac_client.Client.open(
        config["stac_url"], modifier=planetary_computer.sign_inplace
    )
    cutoff = date.fromisoformat(config["cutoff"])
    years = list(range(int(config["first_year"]), cutoff.year + 1))
    composites, clear_counts = [], []
    for year in years:
        start, end = season_window(year, config)
        items = list(
            catalog.search(
                collections=[config["collection"]],
                bbox=[west, south, east, north],
                datetime=f"{start}/{end}",
                query={
                    "platform": {"in": config["platforms"]},
                    "eo:cloud_cover": {"lt": config["max_scene_cloud_percent"]},
                },
            ).items()
        )
        assert_before_cutoff([item.datetime.date() for item in items], cutoff)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            band_stack, clear = year_composite(items, grid, config)
        composites.append(band_stack)
        clear_counts.append(clear)
        print(f"{year}: {len(items)} scenes", flush=True)

    left, top, width, height = grid
    output = ensure_parent(data_path(config["output_composites"]))
    np.savez_compressed(
        output,
        years=np.array(years),
        bands=np.array(BAND_NAMES),
        composites=np.stack(composites),
        clear_counts=np.stack(clear_counts),
        grid=np.array([left, top, config["grid_resolution_m"], width, height]),
        crs=config["grid_crs"],
        cutoff=config["cutoff"],
    )
    write_provenance(
        output,
        source_url=config["stac_url"],
        script_name="scripts/ingest_landsat.py",
        bbox_wgs84=(west, south, east, north),
        crs=config["grid_crs"],
        row_count=len(years),
        config_sha256=file_sha256("configs/ingestion.yaml"),
    )
    print(f"Wrote {len(years)} summer composites to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
