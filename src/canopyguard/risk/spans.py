"""Rank line segments by predicted canopy growth and loss in their corridor.

This is a research prioritisation, not a regulatory clearance or safety
certification. Lines are approximate and have no conductor geometry, so
segments are working pieces and a score says nothing about clearance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import shapely
from numpy.typing import NDArray
from shapely.geometry import LineString, MultiLineString, shape
from shapely.ops import substring

from canopyguard.evaluation.metrics import recall_at_k, spearman


def project_lines(geojson: dict[str, Any], crs: str) -> list[LineString]:
    """Line parts from a GeoJSON collection, projected from EPSG:4326."""
    from pyproj import Transformer

    project = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    parts: list[LineString] = []
    for feature in geojson["features"]:
        geometry = shape(feature["geometry"])
        pieces = geometry.geoms if isinstance(geometry, MultiLineString) else [geometry]
        for piece in pieces:
            x, y = project(*np.asarray(piece.coords)[:, :2].T)
            parts.append(LineString(np.column_stack([x, y])))
    return parts


def cut_segments(lines: list[LineString], length_m: float) -> pd.DataFrame:
    """Cut each line into equal pieces close to the requested length."""
    rows = []
    for line_id, line in enumerate(lines):
        count = max(1, round(line.length / length_m))
        edges = np.linspace(0.0, line.length, count + 1)
        for number, (start, end) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
            rows.append(
                {
                    "segment_id": f"{line_id}-{number}",
                    "geometry": substring(line, start, end),
                    "length_m": float(end - start),
                }
            )
    return pd.DataFrame(rows)


def assign_pixels(
    easting: NDArray, northing: NDArray, segments: pd.DataFrame, half_width_m: float
) -> NDArray[np.int64]:
    """Index of the nearest segment within the half width, else -1."""
    tree = shapely.STRtree(segments["geometry"].to_numpy())
    points = shapely.points(easting, northing)
    pairs = tree.query_nearest(points, max_distance=half_width_m, all_matches=False)
    assigned = np.full(len(points), -1, dtype=np.int64)
    assigned[pairs[0]] = pairs[1]
    return assigned


def segment_table(
    pixels: pd.DataFrame,
    assigned: NDArray[np.int64],
    segments: pd.DataFrame,
    columns: list[str],
    min_pixels: int,
) -> pd.DataFrame:
    """Mean of `columns` over the pixels in each segment's corridor.

    The caller chooses which pixels count (for example canopy only) by passing
    a filtered frame with its matching `assigned` array.
    """
    frame = pixels.assign(segment=assigned)
    frame = frame[frame["segment"] >= 0]
    grouped = frame.groupby("segment")
    table = grouped[columns].mean()
    table["n_pixels"] = grouped.size()
    table = table[table["n_pixels"] >= min_pixels]
    index = table.index.to_numpy()
    table["length_m"] = segments["length_m"].to_numpy()[index]
    centre = shapely.centroid(segments["geometry"].to_numpy()[index])
    table["easting"] = shapely.get_x(centre)
    table["northing"] = shapely.get_y(centre)
    return table


def random_recall(
    labels: NDArray, weights: NDArray, k_fraction: float, draws: int, seed: int
) -> float:
    """Expected recall of a random ranking, by simulation."""
    generator = np.random.default_rng(seed)
    return float(
        np.mean(
            [
                recall_at_k(generator.random(len(labels)), labels, k_fraction, weights)
                for _ in range(draws)
            ]
        )
    )


def block_bootstrap_interval(
    statistic: Callable[[NDArray], float],
    block_ids: NDArray,
    resamples: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    """Percentile interval of a statistic of row indices, resampling blocks."""
    groups = [np.flatnonzero(block_ids == b) for b in np.unique(block_ids)]
    generator = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        chosen = generator.integers(0, len(groups), len(groups))
        indices = np.concatenate([groups[i] for i in chosen])
        try:
            values.append(statistic(indices))
        except ValueError:
            continue
    alpha = (1.0 - confidence) / 2.0
    return float(np.quantile(values, alpha)), float(np.quantile(values, 1.0 - alpha))


def evaluate_ranking(
    table: pd.DataFrame,
    truth_column: str,
    score_columns: dict[str, str],
    headline: str,
    contrasts: list[str],
    config: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    """Recall at k and Spearman per score, with block-bootstrap contrasts.

    Positives are the segments at or above the configured truth quantile.
    Recall is weighted by segment length, so k is a share of line length.
    """
    truth = table[truth_column].to_numpy()
    quantile = float(config["truth"]["high_quantile"])
    labels = (truth >= np.quantile(truth, quantile)).astype(float)
    weights = table["length_m"].to_numpy()
    k_fractions = list(config["ranking"]["k_fractions"])
    scores = {name: table[column].to_numpy() for name, column in score_columns.items()}

    result: dict[str, Any] = {
        "segments": len(table),
        "prevalence": float(labels.mean()),
        "scores": {},
    }
    for name, score in scores.items():
        result["scores"][name] = {"spearman": spearman(score, truth)} | {
            f"recall_at_{int(k * 100)}pct": recall_at_k(score, labels, k, weights)
            for k in k_fractions
        }
    result["scores"]["random"] = {
        f"recall_at_{int(k * 100)}pct": random_recall(
            labels, weights, k, int(config["ranking"]["random_draws"]), seed
        )
        for k in k_fractions
    }

    def recall_gap(first: str, second: str, k: float) -> Callable[[NDArray], float]:
        def gap(i: NDArray) -> float:
            return recall_at_k(
                scores[first][i], labels[i], k, weights[i]
            ) - recall_at_k(scores[second][i], labels[i], k, weights[i])

        return gap

    blocks = table["block"].to_numpy()
    everything = np.arange(len(table))
    result["contrasts"] = {}
    for other in contrasts:
        for k in k_fractions:
            statistic = recall_gap(headline, other, k)
            low, high = block_bootstrap_interval(
                statistic,
                blocks,
                int(config["ranking"]["bootstrap_resamples"]),
                float(config["ranking"]["confidence_level"]),
                seed,
            )
            key = f"{headline}_minus_{other}_recall_at_{int(k * 100)}pct"
            result["contrasts"][key] = {
                "difference": statistic(everything),
                "ci_low": low,
                "ci_high": high,
            }
    return result
