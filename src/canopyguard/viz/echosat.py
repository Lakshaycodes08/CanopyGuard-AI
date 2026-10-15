"""Small visual sample of ECHOSAT heights over the study box."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from canopyguard.io import ensure_parent  # noqa: E402


def _panels(
    data: np.ndarray,
    inside: np.ndarray,
    band_years: list[int],
    check_years: list[int],
    nodata: float,
    figure: dict[str, Any],
    scale_to_m: float,
) -> list[tuple[np.ndarray, str, str, float, float]]:
    first, last = (band_years.index(year) for year in (check_years[0], check_years[-1]))
    shown = inside & (data[first] != nodata) & (data[last] != nodata)
    start, end = (np.where(shown, data[i] * scale_to_m, np.nan) for i in (first, last))
    vmax, limit = figure["height_vmax_m"], figure["change_limit_m"]
    return [
        (start, f"{check_years[0]} height (m)", "viridis", 0, vmax),
        (end, f"{check_years[-1]} height (m)", "viridis", 0, vmax),
        (
            end - start,
            f"{check_years[-1]} minus {check_years[0]} (m)",
            "RdBu",
            -limit,
            limit,
        ),
    ]


def save_sample_figure(
    data: np.ndarray,
    inside: np.ndarray,
    band_years: list[int],
    check_years: list[int],
    nodata: float,
    figure: dict[str, Any],
    scale_to_m: float,
    output: Path,
) -> Path:
    """Plot first-year height, last-year height, and their difference.

    Pixels outside the box or equal to nodata are left blank. The difference
    panel shows a modeled change, not a validated growth signal.
    """
    panels = _panels(data, inside, band_years, check_years, nodata, figure, scale_to_m)
    step = figure["downsample"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 6))
    for axis, (values, title, cmap, low, high) in zip(axes, panels, strict=True):
        image = axis.imshow(values[::step, ::step], cmap=cmap, vmin=low, vmax=high)
        axis.set_title(title)
        axis.axis("off")
        fig.colorbar(image, ax=axis, shrink=0.6)
    fig.tight_layout()
    fig.savefig(ensure_parent(output), dpi=figure["dpi"])
    plt.close(fig)
    return output
