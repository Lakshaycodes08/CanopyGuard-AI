"""Fetch the pinned USGS 3DEP bare-earth DEM tile with provenance."""

from __future__ import annotations

import shutil
from urllib.request import urlopen

import rasterio

from canopyguard.io import ensure_parent, project_root
from canopyguard.provenance import (
    read_provenance,
    sidecar_path,
    study_area_box,
    write_provenance,
)


def fetch_terrain_dem(forecast: dict, study: dict):
    """Keep the exact DEM URL fixed; refuse an unproven local substitute."""
    settings = forecast["stage2_residual_model"]["terrain"]
    output = ensure_parent(project_root() / settings["dem_path"])
    if output.exists():
        if not sidecar_path(output).exists():
            raise FileExistsError(f"DEM lacks provenance: {output}")
        read_provenance(output)
        return output
    partial = output.with_suffix(output.suffix + ".part")
    try:
        with (
            urlopen(settings["dem_url"], timeout=600) as response,  # noqa: S310
            partial.open("wb") as target,
        ):
            shutil.copyfileobj(response, target)
            status = response.status
        partial.replace(output)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    with rasterio.open(output) as source:
        crs = str(source.crs)
    write_provenance(
        output,
        source_url=settings["dem_url"],
        script_name="fetch_terrain_dem.py",
        bbox_wgs84=study_area_box(study),
        crs=crs,
        http_status=status,
    )
    return output
