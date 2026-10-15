"""Write the wire check results, suspect lists and figures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def suspect_rows(table, arrays, epoch, per_group, seed, near_max_m):
    """Top wire-like cells near lines and a random draw of flagged controls."""
    rows, dist, flags = arrays["rows"], arrays["dist"], arrays["flags"][epoch]
    rng = np.random.default_rng(seed)
    flagged = np.flatnonzero(flags["isolated"])
    near = flagged[dist[flagged] < near_max_m]
    near = near[np.argsort(-(flags["top"][near] - flags["upper"][near]))][:per_group]
    far = flagged[dist[flagged] > 250.0]
    far = rng.choice(far, size=min(per_group, len(far)), replace=False)
    out = []
    for group, idx in (("near_line", near), ("control", far)):
        for i in idx:
            r = rows[i]
            out.append(
                [
                    group,
                    epoch,
                    int(table["cell_id"][r]),
                    float(table["x"][r]),
                    float(table["y"][r]),
                    int(table["tile"][r]),
                    round(float(dist[i]), 1),
                    round(float(flags["top"][i]), 2),
                    round(float(flags["upper"][i]), 2),
                ]
            )
    return out


def write_outputs(results, labels_path, cfg, out_dir, table=None):
    """Write results.json, suspects.csv and two figures into out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    arrays = results.pop("_arrays")
    table = table if table is not None else dict(np.load(labels_path))
    near_max = cfg["bands_m"]["near"][1]
    suspects = []
    for epoch in cfg["epochs"]:
        suspects += suspect_rows(
            table, arrays, epoch, cfg["suspects_per_group"], cfg["seed"], near_max
        )
    with open(out / "suspects.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group",
                "epoch",
                "cell_id",
                "x_6339",
                "y_6339",
                "tile",
                "dist_to_line_m",
                "max_height_m",
                "p95_height_m",
            ]
        )
        writer.writerows(suspects)
    write_mask(table, arrays, out / "proposed_mask_near_line_flagged.csv")
    (out / "results.json").write_text(json.dumps(results, indent=2))
    plot_profile(results, cfg, out / "rate_by_distance.png")
    plot_map(table, arrays, cfg, out / "flagged_near_lines.png")


def write_mask(table, arrays, path):
    """Cells within the near band flagged in either epoch, for exclusion."""
    rows, dist, flags = arrays["rows"], arrays["dist"], arrays["flags"]
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "cell_id",
                "x_6339",
                "y_6339",
                "tile",
                "dist_to_line_m",
                "flag_start",
                "flag_end",
            ]
        )
        for i in np.flatnonzero(arrays["mask"]):
            r = rows[i]
            writer.writerow(
                [
                    int(table["cell_id"][r]),
                    float(table["x"][r]),
                    float(table["y"][r]),
                    int(table["tile"][r]),
                    round(float(dist[i]), 1),
                    int(flags["start"]["isolated"][i]),
                    int(flags["end"]["isolated"][i]),
                ]
            )


def plot_profile(results, cfg, path):
    fig, ax = plt.subplots(figsize=(7, 4))
    for epoch in cfg["epochs"]:
        prof = results[epoch]["profile"]
        mids = [(p["from_m"] + p["to_m"]) / 2 for p in prof]
        ax.plot(
            mids,
            [100 * (p["isolated_rate"] or 0) for p in prof],
            marker="o",
            label=f"{epoch} epoch",
        )
    ax.set_xscale("symlog", linthresh=20)
    ax.set_xlabel("Distance to nearest mapped line (m)")
    ax.set_ylabel("Isolated tall cells (% of eligible)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_map(table, arrays, cfg, path):
    rows, dist = arrays["rows"], arrays["dist"]
    x, y = table["x"][rows], table["y"][rows]
    fig, ax = plt.subplots(figsize=(7, 8))
    near = dist < 100
    ax.scatter(x[near], y[near], s=0.3, c="#bbbbbb", linewidths=0)
    for epoch, colour in zip(cfg["epochs"], ("#d95f02", "#1b9e77"), strict=True):
        hit = arrays["flags"][epoch]["isolated"] & near
        ax.scatter(x[hit], y[hit], s=6, c=colour, label=f"flagged, {epoch} epoch")
    ax.set_aspect("equal")
    ax.set_title("Cells within 100 m of a line (grey) and isolated tall cells")
    ax.legend(markerscale=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
