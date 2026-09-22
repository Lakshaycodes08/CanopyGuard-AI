"""Tile the calibration area and draw a stratified sample of work units."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

METRES_PER_DEGREE_LATITUDE = 111320.0
Box = tuple[float, float, float, float]


def tile_grid(box: Box, tile_size_m: float) -> list[Box]:
    """Split a box into tiles of approximately the requested edge length."""
    west, south, east, north = box
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    if tile_size_m <= 0:
        raise ValueError("Tile size must be positive")

    mean_latitude = math.radians((south + north) / 2.0)
    latitude_step = tile_size_m / METRES_PER_DEGREE_LATITUDE
    longitude_step = tile_size_m / (
        METRES_PER_DEGREE_LATITUDE * math.cos(mean_latitude)
    )

    rows = max(1, int((north - south) / latitude_step))
    columns = max(1, int((east - west) / longitude_step))
    return [
        (
            west + column * longitude_step,
            south + row * latitude_step,
            min(west + (column + 1) * longitude_step, east),
            min(south + (row + 1) * latitude_step, north),
        )
        for row in range(rows)
        for column in range(columns)
    ]


def stratified_sample(
    items: Sequence[Any],
    stratum_of: Callable[[Any], str],
    count: int,
    seed: int = 42,
) -> list[Any]:
    """Draw a sample allocated across strata in proportion to their size.

    Every occupied stratum receives at least one item, so a rare stratum is
    never dropped by rounding.
    """
    if count < 1:
        raise ValueError("Sample count must be positive")
    if not items:
        raise ValueError("Cannot sample an empty collection")

    groups: dict[str, list[Any]] = {}
    for item in items:
        groups.setdefault(stratum_of(item), []).append(item)

    if count < len(groups):
        raise ValueError(
            f"Sample count {count} cannot cover {len(groups)} occupied strata"
        )

    allocation = _allocate(groups, count)
    generator = np.random.default_rng(seed)
    sample: list[Any] = []
    for name in sorted(groups):
        members = groups[name]
        take = min(allocation[name], len(members))
        chosen = generator.choice(len(members), size=take, replace=False)
        sample.extend(members[index] for index in sorted(chosen.tolist()))
    return sample


def _allocate(groups: dict[str, list[Any]], count: int) -> dict[str, int]:
    """Give each stratum one item, then share the rest by stratum size."""
    total = sum(len(members) for members in groups.values())
    allocation = {name: 1 for name in groups}
    remaining = count - len(groups)

    if remaining > 0:
        shares = {
            name: remaining * len(members) / total for name, members in groups.items()
        }
        for name in sorted(shares, key=lambda key: -shares[key]):
            take = min(int(shares[name]), remaining)
            allocation[name] += take
            remaining -= take
        for name in sorted(groups, key=lambda key: -len(groups[key])):
            if remaining <= 0:
                break
            allocation[name] += 1
            remaining -= 1
    return allocation


def sample_area_km2(tiles: Sequence[Box]) -> float:
    """Total area of a tile list, using the cosine of each tile's latitude."""
    total = 0.0
    for west, south, east, north in tiles:
        mean_latitude = math.radians((south + north) / 2.0)
        height = (north - south) * METRES_PER_DEGREE_LATITUDE
        width = (east - west) * METRES_PER_DEGREE_LATITUDE * math.cos(mean_latitude)
        total += width * height
    return float(total / 1e6)


def spatial_stratum(box: Box, tile: Box, rows: int = 5, columns: int = 5) -> str:
    """Label a tile by which coarse cell of the enclosing box it falls in.

    Sampling stratified on this label spreads the sample across the area
    instead of letting it clump.
    """
    if rows < 1 or columns < 1:
        raise ValueError("Super grid needs at least one row and one column")

    west, south, east, north = box
    centre_longitude = (tile[0] + tile[2]) / 2.0
    centre_latitude = (tile[1] + tile[3]) / 2.0
    column = min(
        columns - 1, max(0, int((centre_longitude - west) / (east - west) * columns))
    )
    row = min(rows - 1, max(0, int((centre_latitude - south) / (north - south) * rows)))
    return f"r{row}c{column}"
