from __future__ import annotations

from canopyguard.data.gedi import filter_gedi_shots, match_shots_to_segments


def test_filter_gedi_shots() -> None:
    shots = [
        {
            "quality_flag": 1,
            "degrade_flag": 0,
            "sensitivity": 0.98,
            "solar_elevation": -5.0,
        },
        {
            "quality_flag": 0,
            "degrade_flag": 0,
            "sensitivity": 0.98,
            "solar_elevation": -5.0,
        },
        {
            "quality_flag": 1,
            "degrade_flag": 0,
            "sensitivity": 0.90,
            "solar_elevation": -5.0,
        },
        {
            "quality_flag": 1,
            "degrade_flag": 0,
            "sensitivity": 0.98,
            "solar_elevation": 5.0,
        },
    ]
    filtered = filter_gedi_shots(shots, min_sensitivity=0.95, night_only=True)
    assert len(filtered) == 1
    assert filtered[0]["sensitivity"] == 0.98


def test_match_shots_to_segments() -> None:
    shots = [{"lon": -122.0, "lat": 38.0}]
    segments = [{"segment_id": "seg1", "centroid_lon": -122.0, "centroid_lat": 38.0}]
    matched = match_shots_to_segments(shots, segments, max_distance_m=50.0)
    assert len(matched) == 1
    assert matched[0]["segment_id"] == "seg1"
    assert matched[0]["distance_to_centerline_m"] == 0.0
