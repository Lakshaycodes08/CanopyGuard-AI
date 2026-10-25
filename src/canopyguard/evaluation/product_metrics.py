"""Cell-weighted E8 scores and whole-spatial-block uncertainty intervals."""

from __future__ import annotations

import numpy as np


def block_ids(x, y, size_m: float, origin: tuple[float, float]) -> np.ndarray:
    """Assign cells to fixed square blocks anchored to the full label grid."""
    east = np.floor((np.asarray(x) - origin[0]) / size_m).astype(np.int64)
    north = np.floor((np.asarray(y) - origin[1]) / size_m).astype(np.int64)
    _, inverse = np.unique(np.column_stack((east, north)), axis=0, return_inverse=True)
    return inverse


def scores(product, reference) -> dict[str, float]:
    """Score paired heights in metres; positive signed error means product high."""
    error = np.asarray(product, dtype=float) - np.asarray(reference, dtype=float)
    if error.size == 0 or not np.isfinite(error).all():
        raise ValueError("E8 scores require nonempty finite paired heights")
    return {
        "mae_m": float(np.mean(np.abs(error))),
        "median_signed_error_m": float(np.median(error)),
        "mean_signed_error_m": float(np.mean(error)),
        "rmse_m": float(np.sqrt(np.mean(error**2))),
    }


def _bootstrap_medians(error, blocks, multiplicity) -> np.ndarray:
    """Find exact weighted medians by rank without copying millions of cells."""
    ordered = np.sort(error)
    by_block = [
        np.sort(error[blocks == block]) for block in range(multiplicity.shape[1])
    ]
    cells = multiplicity @ np.bincount(blocks)
    weights = np.concatenate((multiplicity, multiplicity))
    ranks = np.concatenate(((cells - 1) // 2, cells // 2))
    low = np.zeros(len(ranks), dtype=np.int64)
    high = np.full(len(ranks), len(ordered) - 1, dtype=np.int64)
    while np.any(low < high):
        middle = (low + high) // 2
        candidates = ordered[middle]
        cumulative = np.zeros(len(ranks), dtype=np.int64)
        for block, values in enumerate(by_block):
            cumulative += weights[:, block] * np.searchsorted(
                values, candidates, side="right"
            )
        above = cumulative > ranks
        high = np.where(above, middle, high)
        low = np.where(above, low, middle + 1)
    middle_values = ordered[low]
    half = len(cells)
    return (middle_values[:half] + middle_values[half:]) / 2


def bootstrap_intervals(
    product,
    reference,
    blocks,
    draws: int,
    seed: int,
) -> dict[str, list[float]] | None:
    """Resample whole spatial blocks and return 95 percent descriptive intervals."""
    error = np.asarray(product, dtype=float) - np.asarray(reference, dtype=float)
    _, block_index = np.unique(np.asarray(blocks), return_inverse=True)
    count = int(block_index.max()) + 1
    if count < 2:
        return None
    rng = np.random.default_rng(seed)
    multiplicity = rng.multinomial(count, np.full(count, 1 / count), size=draws)
    totals = multiplicity @ np.bincount(block_index)
    absolute = multiplicity @ np.bincount(block_index, weights=np.abs(error))
    signed = multiplicity @ np.bincount(block_index, weights=error)
    squared = multiplicity @ np.bincount(block_index, weights=error**2)
    samples = {
        "mae_m": absolute / totals,
        "median_signed_error_m": _bootstrap_medians(error, block_index, multiplicity),
        "mean_signed_error_m": signed / totals,
        "rmse_m": np.sqrt(squared / totals),
    }
    return {
        key: np.percentile(value, [2.5, 97.5]).tolist()
        for key, value in samples.items()
    }


def summarize(product, reference, x, y, settings: dict, origin) -> dict:
    """Return scores and 2 km whole-block intervals for one fixed population."""
    blocks = block_ids(x, y, settings["block_size_m"], origin)
    return {
        "cells": len(product),
        "blocks": int(np.unique(blocks).size),
        "scores": scores(product, reference),
        "intervals_95": bootstrap_intervals(
            product, reference, blocks, settings["bootstrap_draws"], settings["seed"]
        ),
    }


def aggregate_pairs(product, reference, x, y, scale_m: int, settings: dict, origin):
    """Average paired 10 m cells in eligible larger bins, with equal bin weight."""
    east = np.floor((x - origin[0]) / scale_m).astype(np.int64)
    north = np.floor((y - origin[1]) / scale_m).astype(np.int64)
    bins, inverse = np.unique(
        np.column_stack((east, north)), axis=0, return_inverse=True
    )
    occupancy = np.bincount(inverse)
    possible = (scale_m // settings["resolution_m"]) ** 2
    required = int(np.ceil(settings["aggregation_min_valid_fraction"] * possible))
    eligible = occupancy >= required
    if not np.any(eligible):
        raise ValueError(f"No eligible {scale_m} m E8 bins")
    product_mean = np.bincount(inverse, weights=product) / occupancy
    reference_mean = np.bincount(inverse, weights=reference) / occupancy
    centres = origin + (bins[eligible] + 0.5) * scale_m
    counts = occupancy[eligible]
    return product_mean[eligible], reference_mean[eligible], centres, counts


def score_offsets(records, mask, labels, settings, origin) -> tuple[dict, list[dict]]:
    """Score all fixed shifts on one common valid-cell intersection."""
    common = mask.copy()
    for record in records:
        common &= np.isfinite(record["product"])
    if not common.any():
        raise ValueError("No E8 cells are valid at all nine offsets")
    offset_results = []
    for record in records:
        result = summarize(
            record["product"][common],
            labels["p95_end"][common],
            labels["x"][common],
            labels["y"][common],
            settings,
            origin,
        )
        result["alignment"] = record["alignment"]
        result["nodata_cells_before_common_mask"] = int(
            (mask & ~np.isfinite(record["product"])).sum()
        )
        offset_results.append(result)
    ranges = {
        name: [
            min(row["scores"][name] for row in offset_results),
            max(row["scores"][name] for row in offset_results),
        ]
        for name in settings["metrics"]
    }
    return {"common_cells": int(common.sum()), "score_ranges_m": ranges}, offset_results


def resolution_results(product, labels, mask, benchmark, alignment, origin) -> dict:
    """Score fixed 30 m and 100 m paired-cell aggregates."""
    answer = {}
    for scale in benchmark["aggregation_scales_m"]:
        p, r, centres, counts = aggregate_pairs(
            product[mask],
            labels["p95_end"][mask],
            labels["x"][mask],
            labels["y"][mask],
            scale,
            {**benchmark, **alignment},
            origin,
        )
        score = summarize(p, r, centres[:, 0], centres[:, 1], benchmark, origin)
        score["contributing_10m_cells"] = int(counts.sum())
        occupied, frequencies = np.unique(counts, return_counts=True)
        score["occupancy_distribution"] = dict(
            zip(occupied.astype(str).tolist(), frequencies.tolist(), strict=True)
        )
        answer[str(scale)] = score
    return answer


def height_strata(product, labels, mask, settings, origin) -> dict:
    """Score fixed strata of the primary LiDAR p95 reference."""
    edges = np.asarray(settings["height_strata_edges_m"], dtype=float)
    references = labels["p95_end"]
    result = {"below_first_edge": int((mask & (references < edges[0])).sum())}
    for index, low in enumerate(edges):
        high = edges[index + 1] if index + 1 < len(edges) else np.inf
        use = mask & (references >= low) & (references < high)
        key = f"[{low:g},{high:g})"
        if use.any():
            result[key] = summarize(
                product[use],
                references[use],
                labels["x"][use],
                labels["y"][use],
                settings,
                origin,
            )
        else:
            result[key] = {
                "cells": 0,
                "blocks": 0,
                "scores": None,
                "intervals_95": None,
            }
    return result


def forest_map_stratum(product, labels, mask, groups, forest_groups, settings, origin):
    """Describe the primary E8 pairs in 2013 forest map groups."""
    by_group = {}
    for group in forest_groups:
        use = mask & (groups == group)
        if not use.any():
            raise ValueError(f"No E8 primary cells in 2013 map group: {group}")
        by_group[group] = summarize(
            product[use],
            labels["p95_end"][use],
            labels["x"][use],
            labels["y"][use],
            settings,
            origin,
        )
    forest = mask & np.isin(groups, forest_groups)
    pooled = summarize(
        product[forest],
        labels["p95_end"][forest],
        labels["x"][forest],
        labels["y"][forest],
        settings,
        origin,
    )
    return {
        "forest_groups": list(forest_groups),
        "pooled": pooled,
        "by_group": by_group,
        "other_primary_cells": int((mask & ~forest).sum()),
    }
