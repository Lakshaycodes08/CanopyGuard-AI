from __future__ import annotations

import json

import numpy as np

from canopyguard.lidar import pair_points, tile_stats
from canopyguard.lidar.ept import to_web_mercator
from canopyguard.lidar.tile_stats import PointRules

RULES = PointRules((7, 18), 9, 2, 13)
TILES = [(-122.0, 38.0, -121.99, 38.01)]
SETTINGS = {"threads": 2, "max_depth": 3}


def make_fetch():
    x0, y0 = to_web_mercator(-122.01, 37.99)
    x1, y1 = to_web_mercator(-121.97, 38.03)
    meta = {"bounds": [x0, y0, -10, x1, y1, 10]}
    root = {"0-0-0-0": 3, "1-0-0-0": 2}
    requested = []

    def fetch(url: str) -> bytes:
        requested.append(url)
        if url.endswith("ept.json"):
            return json.dumps(meta).encode()
        if url.endswith("0-0-0-0.json"):
            return json.dumps(root).encode()
        return url.encode()

    return fetch, requested


def fake_reader(raw: bytes):
    x, y = to_web_mercator(-121.995, 38.005)
    inside = {
        "x": np.array([x, x]),
        "y": np.array([y, y]),
        "z": np.array([100.0, 108.0]),
    }
    inside["classification"] = np.array([2, 1], dtype=np.uint8)
    inside["flags"] = np.zeros(2, dtype=np.uint8)
    return inside


def test_collect_stats_reads_every_listed_node_and_bins_points() -> None:
    fetch, requested = make_fetch()
    grid = tile_stats.make_tile_grid(TILES, 1)

    stats, counts = pair_points.collect_stats(
        ["PROJECT"], grid, RULES, SETTINGS, fetch, fake_reader
    )

    assert counts["nodes"] == 2
    assert counts["points_listed"] == 5
    assert counts["points_kept"] == 4
    assert stats.point_count[0, 0, 0] == 4
    assert tile_stats.heights_above_ground(stats)[0, 0, 0] == 8.0
    assert any(url.endswith("ept-data/0-0-0-0.laz") for url in requested)


def test_collect_stats_sums_over_several_resources() -> None:
    fetch, _ = make_fetch()
    grid = tile_stats.make_tile_grid(TILES, 1)

    stats, counts = pair_points.collect_stats(
        ["A", "B"], grid, RULES, SETTINGS, fetch, fake_reader
    )

    assert counts["nodes"] == 4
    assert stats.point_count[0, 0, 0] == 8
