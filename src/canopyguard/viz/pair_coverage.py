"""Small map of where two LiDAR acquisitions share usable canopy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from canopyguard.io import ensure_parent  # noqa: E402

Box = tuple[float, float, float, float]
INVALID_COLOUR = "#d9d9d9"


def _rectangles(boxes: list[list[float]]) -> list[Rectangle]:
    return [Rectangle((w, s), e - w, n - s) for w, s, e, n in boxes]


def _tile_colours(rows: list[dict[str, Any]], cells: int) -> list[Any]:
    cmap = plt.get_cmap("YlGn")
    colours = []
    for row in rows:
        if not (row["valid_earlier"] and row["valid_later"]):
            colours.append(INVALID_COLOUR)
        else:
            colours.append(cmap(0.15 + 0.85 * row["undisturbed_cells"] / cells))
    return colours


def _draw_tiles(axis, rows: list[dict[str, Any]], cells: int) -> None:
    patches = PatchCollection(
        _rectangles([row["bounds"] for row in rows]),
        facecolors=_tile_colours(rows, cells),
        edgecolors="none",
    )
    axis.add_collection(patches)


def save_map(report: dict[str, Any], study_bbox: Box, output: Path, dpi: int) -> Path:
    """Overview of the study box and shared patches, plus a zoom on the tiles."""
    rows = report["pair"]["tile_rows"]
    cells = report["tiles"]["cells_per_tile"]
    patches = [patch["bounds"] for patch in report["overlap"]["shared_patches"]]
    fig, (overview, zoom) = plt.subplots(1, 2, figsize=(11, 5.5))

    west, south, east, north = study_bbox
    overview.add_patch(
        Rectangle(
            (west, south),
            east - west,
            north - south,
            fill=False,
            edgecolor="tab:blue",
            linewidth=2,
        )
    )
    overview.text(west, north + 0.01, "study box", color="tab:blue", fontsize=8)
    overview.add_collection(
        PatchCollection(_rectangles(patches), facecolors="#9ecae1", edgecolors="none")
    )
    _draw_tiles(overview, rows, cells)
    xs = [west, *[p[0] for p in patches], *[p[2] for p in patches]]
    ys = [south, north, *[p[1] for p in patches], *[p[3] for p in patches]]
    overview.set_xlim(min(xs) - 0.03, max(xs) + 0.03)
    overview.set_ylim(min(ys) - 0.03, max(ys) + 0.03)
    distance = report["overlap"]["shared_distance_to_study_box_km"]
    overview.set_title(f"Shared ground is {distance:.0f} km from the study box")

    _draw_tiles(zoom, rows, cells)
    tile_boxes = [row["bounds"] for row in rows]
    zoom.set_xlim(
        min(b[0] for b in tile_boxes) - 0.01, max(b[2] for b in tile_boxes) + 0.01
    )
    zoom.set_ylim(
        min(b[1] for b in tile_boxes) - 0.01, max(b[3] for b in tile_boxes) + 0.01
    )
    answer = report["answer"]
    zoom.set_title(
        f"250 m tiles: {answer['valid_both_tiles']} valid in both epochs\n"
        f"usable canopy {answer['usable_canopy_km2']:.1f} km2 (green), grey = not valid"
    )
    for axis in (overview, zoom):
        axis.set_xlabel("longitude")
        axis.set_ylabel("latitude")
        axis.set_aspect(1.0 / 0.78)
    fig.tight_layout()
    fig.savefig(ensure_parent(output), dpi=dpi)
    plt.close(fig)
    return output
