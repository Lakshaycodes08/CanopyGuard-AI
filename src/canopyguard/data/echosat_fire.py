"""Check ECHOSAT band order against the perimeter of a dated fire.

Fire causes abrupt height loss. If the bands run forward in time, large drops
inside a known fire perimeter should peak in the step after the fire year. This
is an independent consistency check on the band order the authors confirmed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from canopyguard.config import require_keys
from canopyguard.data import echosat
from canopyguard.provenance import Box

JsonFetcher = Callable[[str, float], dict[str, Any]]
FIRE_KEYS = ["perimeter_url", "fire_name", "fire_year"]


def build_perimeter_url(fire: dict[str, Any], bbox: Box) -> str:
    """Build the perimeter query for one named fire inside the study box."""
    require_keys(fire, FIRE_KEYS)
    params = {
        "where": f"FIRE_NAME='{fire['fire_name']}' AND YEAR_='{fire['fire_year']}'",
        "geometry": ",".join(str(value) for value in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FIRE_NAME,YEAR_,ALARM_DATE,GIS_ACRES",
        "outSR": "4326",
        "f": "geojson",
    }
    return f"{fire['perimeter_url']}?{urlencode(params)}"


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.load(response)


def fetch_fire_perimeter(
    fire: dict[str, Any],
    bbox: Box,
    timeout_seconds: float,
    fetch_json: JsonFetcher | None = None,
) -> BaseGeometry:
    """Fetch the named fire perimeter and merge its polygons into one shape."""
    fetch = fetch_json or _fetch_json
    page = fetch(build_perimeter_url(fire, bbox), timeout_seconds)
    features = page.get("features")
    if not isinstance(features, list) or not features:
        msg = f"No perimeter found for {fire['fire_name']} {fire['fire_year']}"
        raise ValueError(msg)
    return unary_union([shape(feature["geometry"]) for feature in features])


def count_drops_in_perimeter(
    box: echosat.BoxRead,
    perimeter: BaseGeometry,
    band_years: list[int],
    nodata: float,
    threshold_m: float,
    scale_to_m: float,
) -> dict[str, Any]:
    """Count large drops per consecutive step, and how many fall in the perimeter."""
    lon, lat = echosat.pixel_lonlat(box.transform, box.data.shape[1:], box.crs)
    in_perimeter = box.inside & shapely.contains_xy(perimeter, lon, lat)
    threshold_raw = threshold_m / scale_to_m
    steps = []
    for index in range(len(band_years) - 1):
        valid, change = echosat.step_change(
            box.data[index], box.data[index + 1], box.inside, nodata
        )
        drops = valid & (change < -threshold_raw)
        steps.append(
            {
                "from_year": band_years[index],
                "to_year": band_years[index + 1],
                "drop_pixels": int(drops.sum()),
                "drop_pixels_in_perimeter": int((drops & in_perimeter).sum()),
            }
        )
    return {
        "perimeter_share_of_box": float(in_perimeter.sum() / box.inside.sum()),
        "steps": steps,
    }


def fire_check(
    box: echosat.BoxRead,
    perimeter: BaseGeometry,
    source: dict[str, Any],
) -> dict[str, Any]:
    """Compare the step with the most in-perimeter drops against the fire year.

    A fire late in year Y first shows in the band for year Y + 1, so the
    expected step runs from Y to Y + 1.
    """
    fire = source["fire_check"]
    counts = count_drops_in_perimeter(
        box,
        perimeter,
        list(source["band_years"]),
        source["nodata_value"],
        source["abrupt_change_m"],
        source["height_scale_to_m"],
    )
    peak = max(counts["steps"], key=lambda step: step["drop_pixels_in_perimeter"])
    expected = [fire["fire_year"], fire["fire_year"] + 1]
    return {
        "fire_name": fire["fire_name"],
        "fire_year": fire["fire_year"],
        "perimeter_source": fire["perimeter_url"],
        "expected_step": expected,
        "peak_step": [peak["from_year"], peak["to_year"]],
        "peak_matches_expected": [peak["from_year"], peak["to_year"]] == expected,
        **counts,
    }
