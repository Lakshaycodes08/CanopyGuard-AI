from __future__ import annotations

import math

import numpy as np
import pytest

from canopyguard.data.osm_power import (
    densify,
    near_box,
    overpass_query,
    parse_overpass,
    parse_voltage_kv,
    spans,
)

PAYLOAD = {
    "elements": [
        {"type": "node", "id": 1, "lon": -122.80, "lat": 38.60,
         "tags": {"power": "tower"}},
        {"type": "node", "id": 2, "lon": -122.79, "lat": 38.60},
        {"type": "node", "id": 3, "lon": -122.78, "lat": 38.60,
         "tags": {"power": "tower"}},
        {"type": "node", "id": 4, "lon": -122.77, "lat": 38.60},
        {"type": "way", "id": 10, "nodes": [1, 2, 3, 4],
         "tags": {"power": "line", "voltage": "115000;60000"}},
        {"type": "way", "id": 11, "nodes": [4], "tags": {"power": "line"}},
    ]
}


def test_query_selects_power_ways_in_the_box():
    query = overpass_query((-122.9, 38.4, -122.7, 38.8), ("line", "minor_line"))
    assert '"power"~"^(line|minor_line)$"' in query
    assert "(38.4,-122.9,38.8,-122.7)" in query
    with pytest.raises(ValueError, match="west < east"):
        overpass_query((1.0, 0.0, 0.0, 1.0))


def test_voltage_takes_the_highest_circuit():
    assert parse_voltage_kv("115000;60000") == 115.0
    assert math.isnan(parse_voltage_kv(None))
    assert math.isnan(parse_voltage_kv("unknown"))


def test_lines_carry_coordinates_and_supports():
    lines = parse_overpass(PAYLOAD)
    assert len(lines) == 1
    assert lines[0]["voltage_kv"] == 115.0
    assert lines[0]["support"] == [True, False, True, False]


def test_spans_break_at_supports_and_line_ends():
    pieces = spans(parse_overpass(PAYLOAD))
    assert [p["span_id"] for p in pieces] == ["10-0", "10-1"]
    assert pieces[0]["lon"] == [-122.80, -122.79, -122.78]
    assert pieces[1]["lon"] == [-122.78, -122.77]


def test_densify_bounds_the_spacing():
    points = densify([[0.0, 0.0], [10.0, 0.0]], 3.0)
    assert points[0].tolist() == [0.0, 0.0] and points[-1].tolist() == [10.0, 0.0]
    assert np.max(np.diff(points[:, 0])) <= 3.0
    with pytest.raises(ValueError, match="positive"):
        densify([[0.0, 0.0]], 0.0)


def test_near_box_uses_the_buffer():
    points = np.array([[0.0, 0.0]])
    assert near_box(points, (50.0, -10.0, 60.0, 10.0), 50.0)
    assert not near_box(points, (51.0, -10.0, 60.0, 10.0), 50.0)


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def test_fetch_sends_a_user_agent_and_falls_back(monkeypatch):
    from canopyguard.data.osm_power import fetch_power_lines

    seen = []

    def opener(request, timeout):
        seen.append((request.full_url, request.get_header("User-agent")))
        if "first" in request.full_url:
            raise OSError("HTTP Error 406: Not Acceptable")
        return _Response(b'{"elements": []}')

    payload = fetch_power_lines(
        (-122.9, 38.4, -122.7, 38.8), urls=("https://first", "https://second"),
        opener=opener,
    )
    assert payload == {"elements": []}
    assert all(agent.startswith("CanopyGuard-AI") for _, agent in seen)
    assert [url for url, _ in seen] == ["https://first"] * 2 + ["https://second"]


def test_fetch_reports_every_failure():
    from canopyguard.data.osm_power import fetch_power_lines

    def opener(request, timeout):
        raise OSError("blocked")

    with pytest.raises(RuntimeError, match="No Overpass endpoint answered"):
        fetch_power_lines((-122.9, 38.4, -122.7, 38.8), urls=("https://a",),
                          opener=opener)
