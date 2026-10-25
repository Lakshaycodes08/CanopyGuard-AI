"""Render Chapman-Richards curves as a diagnostic sensitivity figure."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from canopyguard.forecasting.growth_curve import chapman_richards
from canopyguard.io import ensure_parent


def plot_curves(metrics: dict, path) -> None:
    """Show fitted curves, including the forced no-growth region above A."""
    preferred = (
        "Sequoia sempervirens Alliance",
        "Pseudotsuga menziesii Alliance",
        "Quercus agrifolia Alliance",
        "Quercus douglasii Alliance",
        "Umbellularia californica Alliance",
        "Arbutus menziesii Alliance",
    )
    by_name = {row["vegetation_type"]: row for row in metrics["per_type"]}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=160)
    grid = np.linspace(2, 40, 150)
    axes[0].plot(grid, grid, color="black", ls="--", lw=1.2, label="No change")
    axes[1].axhline(0, color="black", ls="--", lw=1.2)
    for name in preferred:
        if name not in by_name:
            continue
        fit = by_name[name]["fit"]
        height = chapman_richards(
            grid, metrics["baseline_years"], fit["A"], fit["k"], fit["c"]
        )
        label = name.replace(" Alliance", "")
        axes[0].plot(grid, height, lw=2, label=label)
        axes[1].plot(grid, height - grid, lw=2, label=label)
    axes[0].set(
        xlabel="2013 p95 canopy height (m)",
        ylabel="Predicted 2022 p95 canopy height (m)",
        title="Chapman-Richards sensitivity: fitted height",
    )
    axes[1].set(
        xlabel="2013 p95 canopy height (m)",
        ylabel="Predicted 9-year gain (m)",
        title="Chapman-Richards sensitivity: gain",
    )
    for axis in axes:
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(ensure_parent(path))
    plt.close(fig)
