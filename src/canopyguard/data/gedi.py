from __future__ import annotations

from typing import Any

from canopyguard.data.spatial import haversine_distance_m


def filter_gedi_shots(
    shots: list[dict[str, Any]],
    min_sensitivity: float = 0.95,
    night_only: bool = True,
) -> list[dict[str, Any]]:
    """Filter raw GEDI shots based on quality flags, SNR, and solar elevation."""
    valid_shots = []
    for shot in shots:
        if shot.get("quality_flag", 0) != 1:
            continue
        if shot.get("degrade_flag", 1) != 0:
            continue
        if float(shot.get("sensitivity", 0.0)) < min_sensitivity:
            continue
        if night_only and float(shot.get("solar_elevation", 0.0)) >= 0.0:
            continue
        valid_shots.append(shot)
    return valid_shots


def match_shots_to_segments(
    shots: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    max_distance_m: float = 50.0,
) -> list[dict[str, Any]]:
    """Associate GEDI laser footprint shots with nearest corridor segments."""
    matched = []
    for shot in shots:
        s_lon = float(shot.get("lon", shot.get("longitude", 0.0)))
        s_lat = float(shot.get("lat", shot.get("latitude", 0.0)))

        best_seg_id = None
        min_dist = float("inf")

        for seg in segments:
            c_lon = float(seg["centroid_lon"])
            c_lat = float(seg["centroid_lat"])
            dist = haversine_distance_m(s_lon, s_lat, c_lon, c_lat)

            if dist < min_dist:
                min_dist = dist
                best_seg_id = seg.get("segment_id")

        if best_seg_id is not None and min_dist <= max_distance_m:
            record = dict(shot)
            record["segment_id"] = best_seg_id
            record["distance_to_centerline_m"] = min_dist
            matched.append(record)

    return matched
