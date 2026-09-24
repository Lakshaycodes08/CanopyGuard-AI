from __future__ import annotations

import math
from typing import Any

from canopyguard.data.spatial import haversine_distance_m


def parse_corridor_geojson(geojson_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse raw GeoJSON into normalized transmission line records."""
    features = geojson_dict.get("features", [])
    records = []

    for feature in features:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        geometry_type = geometry.get("type")

        if not coords or geometry_type not in ("LineString", "MultiLineString"):
            continue

        # A MultiLineString's components are disconnected on the ground (a
        # gap, a jump to another circuit segment); each becomes its own
        # record rather than being merged or dropped.
        components = coords if geometry_type == "MultiLineString" else [coords]

        raw_voltage = props.get("VOLTAGE")
        try:
            voltage = float(raw_voltage) if raw_voltage is not None else 0.0
        except (ValueError, TypeError):
            voltage = 0.0

        base_id = str(props.get("ID") or props.get("OBJECTID") or len(records))
        for index, line_coords in enumerate(components):
            line_id = base_id if len(components) == 1 else f"{base_id}_{index}"
            records.append(
                {
                    "line_id": line_id,
                    "voltage_kv": voltage,
                    "status": str(props.get("STATUS", "UNKNOWN")),
                    "owner": str(props.get("OWNER", "UNKNOWN")),
                    "coordinates": line_coords,
                }
            )

    return records


def segment_corridor_line(
    line_record: dict[str, Any],
    segment_length_m: float = 100.0,
) -> list[dict[str, Any]]:
    """Split a transmission line into discrete longitudinal corridor segments."""
    coords = line_record.get("coordinates", [])
    if len(coords) < 2:
        return []

    line_id = line_record.get("line_id", "unknown")
    voltage_kv = line_record.get("voltage_kv", 0.0)
    segments = []
    seg_idx = 0

    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][:2]
        lon2, lat2 = coords[i + 1][:2]
        span_dist = haversine_distance_m(lon1, lat1, lon2, lat2)

        if span_dist == 0.0:
            continue

        num_sub = max(1, int(math.ceil(span_dist / segment_length_m)))
        for s in range(num_sub):
            f1 = s / num_sub
            f2 = (s + 1) / num_sub
            p1_lon = lon1 + f1 * (lon2 - lon1)
            p1_lat = lat1 + f1 * (lat2 - lat1)
            p2_lon = lon1 + f2 * (lon2 - lon1)
            p2_lat = lat1 + f2 * (lat2 - lat1)

            c_lon = (p1_lon + p2_lon) / 2.0
            c_lat = (p1_lat + p2_lat) / 2.0
            seg_dist = haversine_distance_m(p1_lon, p1_lat, p2_lon, p2_lat)

            segments.append(
                {
                    "segment_id": f"{line_id}_{seg_idx:04d}",
                    "line_id": line_id,
                    "voltage_kv": voltage_kv,
                    "centroid_lon": c_lon,
                    "centroid_lat": c_lat,
                    "start_lon": p1_lon,
                    "start_lat": p1_lat,
                    "end_lon": p2_lon,
                    "end_lat": p2_lat,
                    "segment_length_m": seg_dist,
                }
            )
            seg_idx += 1

    return segments
