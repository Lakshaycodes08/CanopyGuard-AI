from __future__ import annotations

from canopyguard.data.corridors import parse_corridor_geojson, segment_corridor_line


def test_parse_corridor_geojson() -> None:
    geojson = {
        "features": [
            {
                "properties": {"ID": "101", "VOLTAGE": "230"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-122.0, 38.0], [-122.1, 38.1]],
                },
            }
        ]
    }
    records = parse_corridor_geojson(geojson)
    assert len(records) == 1
    assert records[0]["line_id"] == "101"
    assert records[0]["voltage_kv"] == 230.0


def test_segment_corridor_line() -> None:
    # Segment a small distance
    record = {
        "line_id": "line1",
        "voltage_kv": 115.0,
        "coordinates": [[-122.0, 38.0], [-122.0, 38.001]],  # Roughly ~111m
    }
    segments = segment_corridor_line(record, segment_length_m=50.0)
    assert len(segments) > 0
    assert segments[0]["line_id"] == "line1"
