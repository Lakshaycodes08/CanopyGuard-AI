"""Acquisition footprints and the area where two epochs can be compared."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0
Box = tuple[float, float, float, float]


def as_box(west: float, south: float, east: float, north: float) -> Box:
    """Validate and return a west, south, east, north box."""
    if west >= east or south >= north:
        raise ValueError("Require west < east and south < north")
    return (float(west), float(south), float(east), float(north))


def intersect(left: Box, right: Box) -> Box | None:
    """Overlap of two boxes, or None when they do not meet."""
    west = max(left[0], right[0])
    south = max(left[1], right[1])
    east = min(left[2], right[2])
    north = min(left[3], right[3])
    if west >= east or south >= north:
        return None
    return (west, south, east, north)


def intersect_all(boxes: list[Box]) -> Box | None:
    """Overlap common to every box."""
    if not boxes:
        raise ValueError("At least one box is required")
    current: Box | None = boxes[0]
    for box in boxes[1:]:
        if current is None:
            return None
        current = intersect(current, box)
    return current


def area_km2(box: Box) -> float:
    """Approximate box area, using the cosine of the mean latitude."""
    west, south, east, north = box
    mean_latitude = math.radians((south + north) / 2.0)
    height_km = math.radians(north - south) * EARTH_RADIUS_KM
    width_km = math.radians(east - west) * EARTH_RADIUS_KM * math.cos(mean_latitude)
    return float(width_km * height_km)


def probe_grid(box: Box, rows: int, columns: int) -> list[Box]:
    """Split a box into sub-boxes for probing actual acquisition coverage.

    A published acquisition bounding box is the hull of its work units, not
    its coverage. Probing sub-boxes against the catalogue is what establishes
    where an epoch is really present.
    """
    if rows < 1 or columns < 1:
        raise ValueError("Probe grid needs at least one row and one column")

    west, south, east, north = box
    latitude_step = (north - south) / rows
    longitude_step = (east - west) / columns
    return [
        (
            west + column * longitude_step,
            south + row * latitude_step,
            west + (column + 1) * longitude_step,
            south + (row + 1) * latitude_step,
        )
        for row in range(rows)
        for column in range(columns)
    ]


def covered_area_km2(probes: list[Box], present: list[bool]) -> float:
    """Total area of the probe cells where an epoch was found."""
    if len(probes) != len(present):
        raise ValueError("Probe and presence lists must be the same length")
    pairs = zip(probes, present, strict=True)
    return float(sum(area_km2(box) for box, found in pairs if found))


def stratum_shortfall(counts: dict[str, int], minimum: int) -> dict[str, int]:
    """Strata holding fewer cells than the measurement requires."""
    if minimum < 0:
        raise ValueError("Minimum must be non-negative")
    return {name: count for name, count in counts.items() if count < minimum}
