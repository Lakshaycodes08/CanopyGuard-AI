"""Rank line segments by predicted canopy growth in their corridor.

This is a research prioritisation, not a regulatory clearance or safety
certification. Lines are approximate and have no conductor geometry, so
segments are working pieces and the score says nothing about clearance.
"""

from __future__ import annotations

import math
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


def segment_scores(
    pixels: pd.DataFrame,
    assigned: NDArray[np.int64],
    segments: pd.DataFrame,
    prediction_columns: list[str],
    truth: dict[str, Any],
) -> pd.DataFrame:
    """Per-segment truth, survey height and mean predicted growth."""
    frame = pixels.assign(segment=assigned)
    frame = frame[
        (frame["segment"] >= 0) & (frame["canopy_share"] >= truth["min_canopy_share"])
    ]
    grouped = frame.groupby("segment")
    table = grouped[["y", "p95_change", "p95_start", *prediction_columns]].mean()
    table["n_pixels"] = grouped.size()
    table = table[table["n_pixels"] >= truth["min_pixels_per_segment"]]
    table = table.rename(
        columns={"y": "truth_mean_change", "p95_change": "truth_p95_change"}
    )
    table["length_m"] = segments["length_m"].to_numpy()[table.index.to_numpy()]
    centre = shapely.centroid(segments["geometry"].to_numpy()[table.index.to_numpy()])
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


def ranking_metrics(
    score: NDArray,
    truth: NDArray,
    labels: NDArray,
    weights: NDArray,
    k_fractions: list[float],
) -> dict[str, float]:
    result = {"spearman": spearman(score, truth)}
    for k in k_fractions:
        result[f"recall_at_{int(k * 100)}pct"] = recall_at_k(score, labels, k, weights)
    return result


def block_bootstrap_interval(
    statistic: Any,
    block_ids: NDArray,
    resamples: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    """Percentile interval of a statistic of segment indices, resampling blocks."""
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


def half_width_label(half_width_m: float) -> str:
    return f"{int(math.floor(half_width_m))}m"


def evaluate_ranking(
    table: pd.DataFrame, truth_column: str, config: dict[str, Any], seed: int
) -> dict[str, Any]:
    """Recall at k and Spearman for each score, with block-bootstrap contrasts."""
    ranking = config["ranking"]
    quantile = float(config["truth"]["high_growth_quantile"])
    truth = table[truth_column].to_numpy()
    labels = (truth >= np.quantile(truth, quantile)).astype(float)
    weights = table["length_m"].to_numpy()
    k_fractions = list(ranking["k_fractions"])
    models = [*ranking["satellite_only"], *ranking["survey_based"]]
    scores = {name: table[f"pred_{name}"].to_numpy() for name in models}
    scores["current_height_first"] = table["p95_start"].to_numpy()

    result: dict[str, Any] = {
        "segments": len(table),
        "prevalence": float(labels.mean()),
        "scores": {
            name: ranking_metrics(s, truth, labels, weights, k_fractions)
            for name, s in scores.items()
        },
    }
    result["scores"]["random"] = {
        f"recall_at_{int(k * 100)}pct": random_recall(
            labels, weights, k, int(ranking["random_draws"]), seed
        )
        for k in k_fractions
    }
    headline = ranking["headline"]
    blocks = table["block"].to_numpy()
    contrasts = {}
    for other in ("current_height_first", "survey_height_x_eco_median"):
        for k in k_fractions:
            key = f"recall_at_{int(k * 100)}pct"

            def difference(idx: NDArray, k: float = k, other: str = other) -> float:
                first = recall_at_k(scores[headline][idx], labels[idx], k, weights[idx])
                second = recall_at_k(scores[other][idx], labels[idx], k, weights[idx])
                return first - second

            low, high = block_bootstrap_interval(
                difference,
                blocks,
                int(ranking["bootstrap_resamples"]),
                float(ranking["confidence_level"]),
                seed,
            )
            contrasts[f"{headline}_minus_{other}_{key}"] = {
                "difference": difference(np.arange(len(table))),
                "ci_low": low,
                "ci_high": high,
            }
    result["contrasts"] = contrasts
    return result
