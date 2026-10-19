"""Read the returns of one acquisition over a set of tiles into tile statistics."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from canopyguard.lidar import ept_nodes
from canopyguard.lidar.ept import box_to_web_mercator
from canopyguard.lidar.tile_stats import PointRules, TileGrid, TileStats, add_points

PointReader = Callable[[bytes], dict[str, np.ndarray]]
CHUNKS_PER_THREAD = 4


def collect_stats(
    projects: list[str],
    grid: TileGrid,
    rules: PointRules,
    settings: dict[str, Any],
    fetch: ept_nodes.Fetcher,
    read_points: PointReader = ept_nodes.read_node_points,
) -> tuple[TileStats, dict[str, int]]:
    """Statistics of every tile from all resources of an epoch, plus read counts."""
    stats = TileStats(len(grid.tiles), grid.cells)
    counts = {"nodes": 0, "points_listed": 0, "points_kept": 0}
    tiles_3857 = [box_to_web_mercator(tile) for tile in grid.tiles]
    threads = int(settings["threads"])
    for project in projects:
        meta = json.loads(fetch(ept_nodes.resource_url(project, "ept.json")))
        cube = (
            meta["bounds"][0],
            meta["bounds"][1],
            meta["bounds"][3],
            meta["bounds"][4],
        )
        root = json.loads(
            fetch(ept_nodes.resource_url(project, "ept-hierarchy", "0-0-0-0.json"))
        )
        nodes = ept_nodes.list_nodes(
            cube,
            root,
            ept_nodes.subtree_fetcher(project, fetch, threads),
            tiles_3857,
            int(settings["max_depth"]),
        )
        counts["nodes"] += len(nodes)
        counts["points_listed"] += sum(count for _, count in nodes)
        counts["points_kept"] += _read_nodes(
            project, nodes, grid, stats, rules, fetch, read_points, threads
        )
    return stats, counts


def _read_nodes(project, nodes, grid, stats, rules, fetch, read_points, threads) -> int:
    def load(item: tuple[str, int]) -> dict[str, np.ndarray]:
        return read_points(
            fetch(ept_nodes.resource_url(project, "ept-data", f"{item[0]}.laz"))
        )

    kept = 0
    step = threads * CHUNKS_PER_THREAD
    with ThreadPoolExecutor(threads) as pool:
        for start in range(0, len(nodes), step):
            for points in pool.map(load, nodes[start : start + step]):
                kept += add_points(stats, grid, points, rules)
    return kept
