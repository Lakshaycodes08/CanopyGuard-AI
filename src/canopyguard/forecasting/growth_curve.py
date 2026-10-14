"""Chapman-Richards height growth and spatially blocked comparison baselines."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from canopyguard.evaluation.blocks import assign_blocks, systematic_folds


def chapman_richards(
    start: np.ndarray, dt: float, a: float, k: float, c: float
) -> np.ndarray:
    """Age-free Chapman-Richards height at the second survey."""
    height = np.asarray(start, dtype=float)
    if dt <= 0 or a <= 0 or k <= 0 or c <= 1:
        raise ValueError("Growth curve requires dt, A, k > 0 and c > 1")
    if np.any(height < 0):
        raise ValueError("Start heights must be nonnegative")
    base = 1 - (1 - np.power(height / a, 1 / c)) * np.exp(-k * dt)
    return a * np.power(base, c)


def fit_growth_curve(
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    settings: dict,
    *,
    maximum_start_height: float,
) -> dict[str, float]:
    """Robustly fit A, k, c using training outcomes only."""
    x = np.asarray(start, dtype=float)
    y = np.asarray(end, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0)
    if valid.sum() < settings["min_fit_cells"]:
        raise ValueError("Too few training cells for a growth curve")
    x, y = x[valid], y[valid]
    lower_a = max(float(x.max()), float(y.max()), maximum_start_height)
    lower_a += settings["a_margin_m"]
    upper_a = settings["a_upper_m"]
    if lower_a >= upper_a:
        raise ValueError("Observed height exceeds the configured A ceiling")
    lower = [lower_a, settings["k_bounds"][0], settings["c_bounds"][0]]
    upper = [upper_a, settings["k_bounds"][1], settings["c_bounds"][1]]
    initial = [
        min(max(lower_a + 5, lower_a * 1.2), upper_a - 0.1),
        settings["initial_k"],
        settings["initial_c"],
    ]
    initial = np.clip(initial, np.array(lower) + 1e-6, np.array(upper) - 1e-6)
    result = least_squares(
        lambda values: chapman_richards(x, dt, *values) - y,
        x0=initial,
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=settings["soft_l1_scale_m"],
        max_nfev=settings["max_nfev"],
    )
    if not result.success:
        raise ValueError(f"Growth fit failed: {result.message}")
    a, k, c = result.x
    return {
        "A": float(a),
        "k": float(k),
        "c": float(c),
        "n": int(len(x)),
        "a_at_upper_bound": bool(a > upper_a * settings["a_upper_warning_fraction"]),
    }


def _training_scope(
    model_group: str,
    broad_group: str,
    train: np.ndarray,
    groups: np.ndarray,
    broad: np.ndarray,
    minimum: int,
) -> tuple[str, np.ndarray]:
    own = train & (groups == model_group)
    if not model_group.startswith("group:") and own.sum() >= minimum:
        return "type:" + model_group, own
    pooled = train & (broad == broad_group)
    if pooled.sum() < minimum:
        raise ValueError(f"Too few training cells for broad group {broad_group}")
    return "broad:" + broad_group, pooled


def blocked_predictions(
    frame,
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    block_size_m: float,
    settings: dict,
) -> dict:
    """Out-of-fold curve and training-median predictions on held-out blocks."""
    block_ids = assign_blocks(frame["x"], frame["y"], block_size_m)
    folds = systematic_folds(block_ids, settings["folds"], settings["seed"])
    group = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    curve = np.full(len(frame), np.nan)
    median = np.full(len(frame), np.nan)
    scopes: dict[str, int] = {}
    for fold in range(settings["folds"]):
        train, test = folds != fold, folds == fold
        cache = {}
        for model_group in np.unique(group[test]):
            use = test & (group == model_group)
            broad_group = broad[np.flatnonzero(use)[0]]
            scope, fit_rows = _training_scope(
                model_group,
                broad_group,
                train,
                group,
                broad,
                settings["min_fit_cells"],
            )
            if scope not in cache:
                population = (
                    group == model_group
                    if scope.startswith("type:")
                    else broad == broad_group
                )
                fit = fit_growth_curve(
                    start[fit_rows],
                    end[fit_rows],
                    dt,
                    settings,
                    maximum_start_height=float(np.max(start[population])),
                )
                median_growth = float(np.median(end[fit_rows] - start[fit_rows]))
                cache[scope] = fit, median_growth
            fit, median_growth = cache[scope]
            curve[use] = chapman_richards(start[use], dt, fit["A"], fit["k"], fit["c"])
            median[use] = start[use] + median_growth
            scopes[scope] = scopes.get(scope, 0) + int(use.sum())
    if not np.isfinite(curve).all() or not np.isfinite(median).all():
        raise ValueError("Some held-out cells lack growth predictions")
    return {
        "blocks": block_ids,
        "folds": folds,
        "curve": curve,
        "median": median,
        "fit_scope_counts": scopes,
    }


def block_mae_interval(
    curve_error: np.ndarray,
    no_change_error: np.ndarray,
    blocks: np.ndarray,
    *,
    draws: int,
    seed: int,
) -> dict[str, float]:
    """Bootstrap the paired MAE difference by resampling whole map blocks."""
    if not (len(curve_error) == len(no_change_error) == len(blocks)):
        raise ValueError("Errors and blocks must have equal length")
    _, inverse = np.unique(blocks, return_inverse=True)
    block_count = int(inverse.max()) + 1
    if block_count < 2:
        raise ValueError("Need at least two spatial blocks")
    counts = np.bincount(inverse, minlength=block_count)
    curve_totals = np.bincount(
        inverse, weights=np.abs(curve_error), minlength=block_count
    )
    no_change_totals = np.bincount(
        inverse, weights=np.abs(no_change_error), minlength=block_count
    )
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, block_count, size=(draws, block_count))
    total_cells = counts[samples].sum(axis=1)
    differences = (
        curve_totals[samples].sum(axis=1) - no_change_totals[samples].sum(axis=1)
    ) / total_cells
    observed = float((curve_totals.sum() - no_change_totals.sum()) / counts.sum())
    low, high = np.quantile(differences, [0.025, 0.975])
    return {
        "difference_m": observed,
        "ci_low_m": float(low),
        "ci_high_m": float(high),
        "blocks": block_count,
        "draws": draws,
    }
