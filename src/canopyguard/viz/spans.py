"""Maps of predicted and observed corridor values on line segments."""

from __future__ import annotations

import numpy as np
import pandas as pd

GRAY = "#c9ced6"
INK = "#2b2f36"


def draw_segments(ax, segments: pd.DataFrame, values: pd.Series, norm, cmap) -> None:
    """Gray backdrop for every segment, coloured by value where one exists."""
    for geometry in segments["geometry"]:
        x, y = geometry.xy
        ax.plot(np.asarray(x) / 1000.0, np.asarray(y) / 1000.0, color=GRAY, lw=1.0)
    for index, value in values.dropna().items():
        x, y = segments.loc[index, "geometry"].xy
        ax.plot(
            np.asarray(x) / 1000.0,
            np.asarray(y) / 1000.0,
            color=cmap(norm(value)),
            lw=3.0,
            solid_capstyle="butt",
        )


def forecast_figure(
    regions: dict[str, pd.DataFrame],
    segments: dict[str, pd.DataFrame],
    predicted: str,
    observed: str,
    title: str,
    unit: str,
    cmap_name: str,
):
    """Predicted and observed side by side for each region, one shared scale."""
    import matplotlib.pyplot as plt
    from matplotlib import colors

    pooled = pd.concat(
        [t[[predicted, observed]] for t in regions.values()], ignore_index=True
    )
    low = float(np.nanpercentile(pooled.to_numpy(), 2))
    high = float(np.nanpercentile(pooled.to_numpy(), 98))
    norm = colors.Normalize(vmin=min(low, 0.0), vmax=high)
    cmap = plt.get_cmap(cmap_name)
    rows = len(regions)
    figure, axes = plt.subplots(
        rows, 2, figsize=(8.5, 3.6 * rows), squeeze=False, constrained_layout=True
    )
    for row, (name, table) in enumerate(regions.items()):
        for column, (field, label) in enumerate(
            ((predicted, "Predicted"), (observed, "Observed"))
        ):
            ax = axes[row][column]
            draw_segments(ax, segments[name], table[field], norm, cmap)
            ax.set_aspect("equal")
            ax.set_title(f"{name}: {label}", fontsize=10, color=INK, loc="left")
            ax.tick_params(labelsize=7, colors=INK)
            ax.set_xlabel("Easting (km)", fontsize=8, color=INK)
            ax.set_ylabel("Northing (km)", fontsize=8, color=INK)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    bar = figure.colorbar(scalar, ax=axes, shrink=0.5, pad=0.02)
    bar.set_label(unit, fontsize=9, color=INK)
    figure.suptitle(title, fontsize=11, color=INK, x=0.02, ha="left")
    return figure
