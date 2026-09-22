"""Access to USGS 3DEP Entwine Point Tiles by bounding box.

3DEP point clouds are published as Entwine resources on public object storage.
PDAL reads a requested window directly over HTTPS, so no point-cloud file is
downloaded. The resources are indexed in EPSG:3857, so a request box is
converted to Web Mercator before it is sent and the points are reprojected to
the working frame afterwards.
"""

from __future__ import annotations

import math
from typing import Any

EPT_BASE = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public"
WEB_MERCATOR_RADIUS_M = 6378137.0
MAX_MERCATOR_LATITUDE_DEG = 85.05112878

Box = tuple[float, float, float, float]


def ept_url(project: str) -> str:
    """Entwine resource URL for a 3DEP project short name."""
    if not project or "/" in project:
        raise ValueError("Project must be a bare 3DEP project name")
    return f"{EPT_BASE}/{project}/ept.json"


def to_web_mercator(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert one geographic coordinate to EPSG:3857 metres."""
    if abs(latitude) > MAX_MERCATOR_LATITUDE_DEG:
        raise ValueError("Latitude is outside the Web Mercator domain")
    x = WEB_MERCATOR_RADIUS_M * math.radians(longitude)
    y = WEB_MERCATOR_RADIUS_M * math.log(
        math.tan(math.pi / 4.0 + math.radians(latitude) / 2.0)
    )
    return x, y


def box_to_web_mercator(box: Box) -> Box:
    """Convert a west, south, east, north box to EPSG:3857 metres."""
    west, south, east, north = box
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    min_x, min_y = to_web_mercator(west, south)
    max_x, max_y = to_web_mercator(east, north)
    return (min_x, min_y, max_x, max_y)


def pdal_bounds(box_3857: Box) -> str:
    """Format a projected box as a PDAL bounds string."""
    min_x, min_y, max_x, max_y = box_3857
    return f"([{min_x},{max_x}],[{min_y},{max_y}])"


def mercator_scale(latitude_deg: float) -> float:
    """Web Mercator length inflation at a latitude, which is 1 over cos."""
    if abs(latitude_deg) > MAX_MERCATOR_LATITUDE_DEG:
        raise ValueError("Latitude is outside the Web Mercator domain")
    return 1.0 / math.cos(math.radians(latitude_deg))


def parse_ept(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the fields the pipeline needs out of an Entwine metadata document."""
    for key in ("bounds", "points", "srs"):
        if key not in payload:
            raise ValueError(f"Entwine metadata is missing {key}")

    bounds = payload["bounds"]
    conforming = payload.get("boundsConforming", bounds)
    return {
        "points": int(payload["points"]),
        "bounds": [float(value) for value in bounds],
        "bounds_conforming": [float(value) for value in conforming],
        "horizontal_epsg": str(payload["srs"].get("horizontal", "")),
        "span": int(payload.get("span", 0)),
        "data_type": payload.get("dataType"),
    }


def return_density(points: int, survey_area_km2: float) -> float:
    """Returns per square metre over the stated survey area.

    This is total returns, not pulses. A single pulse yields several returns
    and swath overlap adds more, so this figure runs well above the nominal
    pulse density quoted in an acquisition specification. Epochs are only
    comparable when the same quantity is used for both.
    """
    if points <= 0 or survey_area_km2 <= 0:
        raise ValueError("Point count and survey area must be positive")
    return float(points / (survey_area_km2 * 1e6))


def pulse_density(nominal_pulse_spacing_m: float) -> float:
    """Pulses per square metre implied by a nominal pulse spacing."""
    if nominal_pulse_spacing_m <= 0:
        raise ValueError("Nominal pulse spacing must be positive")
    return float(1.0 / nominal_pulse_spacing_m**2)


def reader_stage(project: str, box: Box, threads: int = 4) -> dict[str, Any]:
    """PDAL reader fetching only the requested window of a 3DEP resource."""
    if threads < 1:
        raise ValueError("Thread count must be positive")
    return {
        "type": "readers.ept",
        "filename": ept_url(project),
        "bounds": pdal_bounds(box_to_web_mercator(box)),
        "threads": int(threads),
    }
