"""Power line geometry and spans from OpenStreetMap.

A span is the stretch of line between two consecutive supports (tower, pole,
portal or terminal). The Overpass response is parsed without network access,
so everything except `fetch_power_lines` is testable offline.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SUPPORTS = {"tower", "pole", "portal", "terminal"}


def overpass_query(
    bbox: tuple[float, float, float, float],
    kinds: tuple[str, ...] = ("line",),
    timeout_s: int = 180,
) -> str:
    """Overpass QL for power ways of the given kinds and their nodes."""
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    if not kinds:
        raise ValueError("At least one power kind is required")
    pattern = "|".join(sorted(set(kinds)))
    return (
        f"[out:json][timeout:{int(timeout_s)}];"
        f'(way["power"~"^({pattern})$"]({south},{west},{north},{east}););'
        "(._;>;);out body;"
    )


def parse_voltage_kv(value: Any) -> float:
    """Highest voltage in kilovolts from an OSM voltage tag, else not-a-number."""
    if value is None:
        return math.nan
    best = math.nan
    for part in str(value).replace(",", ";").split(";"):
        try:
            volts = float(part.strip())
        except ValueError:
            continue
        kv = volts / 1000.0
        best = kv if math.isnan(best) else max(best, kv)
    return best


def parse_overpass(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Power ways with their node coordinates and support flags."""
    nodes = {}
    for element in payload.get("elements", []):
        if element.get("type") == "node":
            tags = element.get("tags", {})
            nodes[element["id"]] = (
                float(element["lon"]),
                float(element["lat"]),
                tags.get("power") in SUPPORTS,
            )
    lines = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        members = [nodes[n] for n in element.get("nodes", []) if n in nodes]
        if len(members) < 2:
            continue
        tags = element.get("tags", {})
        lines.append(
            {
                "id": int(element["id"]),
                "power": tags.get("power", ""),
                "voltage_kv": parse_voltage_kv(tags.get("voltage")),
                "operator": tags.get("operator", ""),
                "lon": [m[0] for m in members],
                "lat": [m[1] for m in members],
                "support": [m[2] for m in members],
            }
        )
    return lines


def spans(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split every line at its supports; both line ends always close a span."""
    result = []
    for line in lines:
        count = len(line["lon"])
        breaks = [
            i for i in range(count) if i in (0, count - 1) or line["support"][i]
        ]
        for number, (a, b) in enumerate(zip(breaks, breaks[1:], strict=False)):
            result.append(
                {
                    "span_id": f"{line['id']}-{number}",
                    "line_id": line["id"],
                    "power": line["power"],
                    "voltage_kv": line["voltage_kv"],
                    "lon": line["lon"][a : b + 1],
                    "lat": line["lat"][a : b + 1],
                }
            )
    return result


def densify(xy: ArrayLike, step_m: float) -> NDArray[np.float64]:
    """Points along a projected polyline no further apart than the step."""
    points = np.asarray(xy, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 1:
        raise ValueError("Polyline must be an N by 2 array")
    if step_m <= 0:
        raise ValueError("Step must be positive")
    out = [points[:1]]
    for start, end in zip(points[:-1], points[1:], strict=False):
        length = float(np.hypot(*(end - start)))
        count = max(1, math.ceil(length / step_m))
        fraction = np.arange(1, count + 1, dtype=np.float64)[:, None] / count
        out.append(start + fraction * (end - start))
    return np.vstack(out)


def near_box(
    points: ArrayLike, box: tuple[float, float, float, float], buffer_m: float
) -> bool:
    """Whether any point lies within the buffer-expanded projected box."""
    xy = np.asarray(points, dtype=np.float64)
    min_x, min_y, max_x, max_y = box
    return bool(
        np.any(
            (xy[:, 0] >= min_x - buffer_m)
            & (xy[:, 0] <= max_x + buffer_m)
            & (xy[:, 1] >= min_y - buffer_m)
            & (xy[:, 1] <= max_y + buffer_m)
        )
    )


def fetch_power_lines(
    bbox: tuple[float, float, float, float],
    kinds: tuple[str, ...] = ("line",),
    url: str = OVERPASS_URL,
    timeout_s: int = 180,
) -> dict[str, Any]:
    """Overpass response for the power ways inside a box."""
    import json
    import urllib.parse
    import urllib.request

    body = urllib.parse.urlencode({"data": overpass_query(bbox, kinds, timeout_s)})
    request = urllib.request.Request(url, data=body.encode("utf-8"))
    with urllib.request.urlopen(request, timeout=timeout_s + 30) as response:
        return json.loads(response.read().decode("utf-8"))
