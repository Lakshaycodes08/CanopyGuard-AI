"""List and read the point-cloud nodes of a 3DEP Entwine resource over tiles.

An Entwine octree stores each point in the shallowest node with room for it, so
every node from the root down to the depth limit that meets a tile can hold
points inside it. The hierarchy files say which nodes exist and how many points
each holds, without reading any point.
"""

from __future__ import annotations

import http.client
import io
import json
import time
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from canopyguard.lidar.ept import EPT_BASE

Box = tuple[float, float, float, float]
Fetcher = Callable[[str], bytes]
ROOT = "0-0-0-0"
POINT_FIELDS = ("x", "y", "z", "classification", "flags")


def make_fetcher(timeout_s: float, retries: int) -> Fetcher:
    """Return a function that downloads a URL, retrying transient failures."""

    def fetch(url: str) -> bytes:
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=timeout_s) as response:  # noqa: S310
                    return response.read()
            except (OSError, http.client.HTTPException):
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("unreachable")

    return fetch


def resource_url(project: str, *parts: str) -> str:
    """URL of a file inside a 3DEP Entwine resource."""
    if not project or "/" in project:
        raise ValueError("Project must be a bare 3DEP project name")
    return "/".join([EPT_BASE, project, *parts])


def parse_key(key: str) -> tuple[int, int, int, int]:
    """Depth and x, y, z index of an octree node key such as 5-3-2-1."""
    depth, x, y, z = (int(part) for part in key.split("-"))
    return depth, x, y, z


def node_box(cube: Box, key: str) -> Box:
    """Horizontal extent of a node in the resource's Web Mercator frame."""
    depth, x, y, _ = parse_key(key)
    edge = (cube[2] - cube[0]) / 2**depth
    return (
        cube[0] + x * edge,
        cube[1] + y * edge,
        cube[0] + (x + 1) * edge,
        cube[1] + (y + 1) * edge,
    )


def _meets(box: Box, tiles: list[Box]) -> bool:
    return any(
        not (
            box[0] >= tile[2]
            or box[2] <= tile[0]
            or box[1] >= tile[3]
            or box[3] <= tile[1]
        )
        for tile in tiles
    )


def children(key: str) -> list[str]:
    """The eight child keys of a node."""
    depth, x, y, z = parse_key(key)
    return [
        f"{depth + 1}-{2 * x + dx}-{2 * y + dy}-{2 * z + dz}"
        for dx in (0, 1)
        for dy in (0, 1)
        for dz in (0, 1)
    ]


def list_nodes(
    cube: Box,
    hierarchy: dict[str, int],
    fetch_subtrees: Callable[[list[str]], dict[str, int]],
    tiles: list[Box],
    max_depth: int,
) -> list[tuple[str, int]]:
    """Nodes holding points that meet any tile, down to a depth limit.

    `hierarchy` is the root hierarchy file. An entry of -1 marks a subtree kept
    in its own file, which `fetch_subtrees` returns for a batch of keys so the
    downloads can run in parallel.
    """
    found: list[tuple[str, int]] = []
    frontier = [ROOT]
    while frontier:
        frontier = [key for key in frontier if _meets(node_box(cube, key), tiles)]
        pending = [key for key in frontier if hierarchy.get(key) == -1]
        if pending:
            hierarchy.update(fetch_subtrees(pending))
        next_frontier: list[str] = []
        for key in frontier:
            count = hierarchy.get(key, 0)
            if count > 0:
                found.append((key, count))
            if parse_key(key)[0] < max_depth:
                next_frontier.extend(c for c in children(key) if c in hierarchy)
        frontier = next_frontier
    return found


def subtree_fetcher(project: str, fetch: Fetcher, threads: int):
    """Build a batch downloader for hierarchy subtree files."""

    def fetch_subtrees(keys: Iterable[str]) -> dict[str, int]:
        def one(key: str) -> dict[str, int]:
            return json.loads(
                fetch(resource_url(project, "ept-hierarchy", f"{key}.json"))
            )

        merged: dict[str, int] = {}
        with ThreadPoolExecutor(threads) as pool:
            for subtree in pool.map(one, list(keys)):
                merged.update(subtree)
        return merged

    return fetch_subtrees


def read_node_points(raw: bytes) -> dict[str, np.ndarray]:
    """Decode a compressed LAS node into plain arrays.

    This is the only function here that needs `laspy` with a LAZ backend.
    """
    import laspy

    las = laspy.read(io.BytesIO(raw))
    flags = getattr(las, "classification_flags", None)
    return {
        "x": np.asarray(las.x, dtype=np.float64),
        "y": np.asarray(las.y, dtype=np.float64),
        "z": np.asarray(las.z, dtype=np.float64),
        "classification": np.asarray(las.classification, dtype=np.uint8),
        "flags": np.asarray(flags, dtype=np.uint8)
        if flags is not None
        else np.zeros(len(las.x), dtype=np.uint8),
    }
