"""Chapman-Richards height growth and spatially blocked comparison baselines."""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

from canopyguard.evaluation.blocks import assign_blocks, systematic_folds
from canopyguard.forecasting.growth_prior import training_scope


def chapman_richards(
    start: np.ndarray, dt: float, a: float | np.ndarray, k: float, c: float
) -> np.ndarray:
    """Age-free Chapman-Richards height at the second survey."""
    height = np.asarray(start, dtype=float)
    ceiling = np.asarray(a, dtype=float)
    if dt <= 0 or np.any(ceiling <= 0) or k <= 0 or c <= 1:
        raise ValueError("Growth curve requires dt, A, k > 0 and c > 1")
    if np.any(height < 0):
        raise ValueError("Start heights must be nonnegative")
    active = np.minimum(height, ceiling)
    base = 1 - (1 - np.power(active / ceiling, 1 / c)) * np.exp(-k * dt)
    fitted = ceiling * np.power(base, c)
    return np.where(height >= ceiling, height, fitted)


def fit_growth_curve(
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    settings: dict,
    *,
    max_height_m: float | np.ndarray,
) -> dict[str, float]:
    """Fit k and c with a supplied height ceiling."""
    x = np.asarray(start, dtype=float)
    y = np.asarray(end, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0)
    if valid.sum() < settings["min_fit_cells"]:
        raise ValueError("Too few training cells for a growth curve")
    ceiling = np.broadcast_to(np.asarray(max_height_m, dtype=float), x.shape)
    if not np.isfinite(ceiling).all() or np.any(ceiling <= 0):
        raise ValueError("A must be a positive, finite height")
    x, y, ceiling = x[valid], y[valid], ceiling[valid]
    if (x < ceiling).sum() < 3:
        raise ValueError("Too few training cells below fixed A")
    lower = [settings["k_bounds"][0], settings["c_bounds"][0]]
    upper = [settings["k_bounds"][1], settings["c_bounds"][1]]
    result = least_squares(
        lambda values: chapman_richards(x, dt, ceiling, *values) - y,
        x0=[settings["initial_k"], settings["initial_c"]],
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=settings["soft_l1_scale_m"],
        max_nfev=settings["max_nfev"],
    )
    if not result.success:
        raise ValueError(f"Growth fit failed: {result.message}")
    k, c = result.x
    return {
        "A": float(ceiling[0]) if np.all(ceiling == ceiling[0]) else None,
        "k": float(k),
        "c": float(c),
        "n": int(len(x)),
        "k_at_bound": bool(np.isclose(k, lower[0]) or np.isclose(k, upper[0])),
        "c_at_bound": bool(np.isclose(c, lower[1]) or np.isclose(c, upper[1])),
    }


def fit_free_growth_curve(
    start: np.ndarray, end: np.ndarray, dt: float, settings: dict
) -> dict[str, float]:
    """Retain the former free-A fit as a sensitivity calculation."""
    x = np.asarray(start, dtype=float)
    y = np.asarray(end, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0)
    if valid.sum() < settings["min_fit_cells"]:
        raise ValueError("Too few training cells for a growth curve")
    x, y = x[valid], y[valid]
    lower_a = max(float(x.max()), float(y.max()))
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
        "k_at_bound": bool(np.isclose(k, lower[1]) or np.isclose(k, upper[1])),
        "c_at_bound": bool(np.isclose(c, lower[2]) or np.isclose(c, upper[2])),
    }


def class_heights(
    names: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    settings: dict,
    mode: str,
) -> dict[str, float]:
    """Choose class A from literature or the training pair's upper tail."""
    if mode not in ("posthoc", "literature", "record"):
        raise ValueError(f"Unknown A mode: {mode}")
    heights = dict(settings["max_height_m"])
    if mode == "record":
        heights.update(settings["record_tree_height_m"])
    missing = sorted({name for name in names if heights.get(name) is None})
    if missing:
        raise ValueError(f"Unconfirmed maximum height for: {', '.join(missing)}")
    if mode == "posthoc":
        paired_max = np.maximum(start, end)
        quantile = settings["training_height_quantile"]
        return {
            name: max(
                float(heights[name]),
                float(np.quantile(paired_max[names == name], quantile)),
            )
            for name in np.unique(names)
        }
    return {name: float(heights[name]) for name in np.unique(names)}


def blocked_predictions(
    frame,
    start: np.ndarray,
    end: np.ndarray,
    dt: float,
    block_size_m: float,
    settings: dict,
    *,
    a_mode: str = "literature",
) -> dict:
    """Out-of-fold curve and training-median predictions on held-out blocks."""
    block_ids = assign_blocks(frame["x"], frame["y"], block_size_m)
    folds = systematic_folds(block_ids, settings["folds"], settings["seed"])
    group = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    names = frame["vegetation_type"].to_numpy()
    curve = np.full(len(frame), np.nan)
    median = np.full(len(frame), np.nan)
    fold_a = np.full(len(frame), np.nan)
    literature_fallback = np.zeros(len(frame), dtype=bool)
    scopes: dict[str, int] = {}
    for fold in range(settings["folds"]):
        train, test = folds != fold, folds == fold
        cache = {}
        for model_group in np.unique(group[test]):
            use = test & (group == model_group)
            broad_group = broad[np.flatnonzero(use)[0]]
            scope, fit_rows = training_scope(
                model_group,
                broad_group,
                train,
                group,
                broad,
                settings["min_fit_cells"],
            )
            if scope not in cache:
                if a_mode == "free":
                    fit = fit_free_growth_curve(
                        start[fit_rows], end[fit_rows], dt, settings
                    )
                    ceilings = None
                else:
                    ceilings = class_heights(
                        names[fit_rows],
                        start[fit_rows],
                        end[fit_rows],
                        settings,
                        a_mode,
                    )
                    a = np.array([ceilings[name] for name in names[fit_rows]])
                    fit = fit_growth_curve(
                        start[fit_rows], end[fit_rows], dt, settings, max_height_m=a
                    )
                median_growth = float(np.median(end[fit_rows] - start[fit_rows]))
                cache[scope] = fit, median_growth, ceilings
            fit, median_growth, ceilings = cache[scope]
            if ceilings is not None:
                training_names = np.unique(names[fit_rows])
                absent = ~np.isin(names[use], training_names)
                literature_fallback[use] = absent
                fallback_heights = dict(settings["max_height_m"])
                if a_mode == "record":
                    fallback_heights.update(settings["record_tree_height_m"])
                for name in np.unique(names[use][absent]):
                    if fallback_heights.get(name) is None:
                        raise ValueError(f"Unconfirmed maximum height for: {name}")
                    ceilings[name] = float(fallback_heights[name])
            a = (
                fit["A"]
                if ceilings is None
                else np.array([ceilings[name] for name in names[use]])
            )
            fold_a[use] = a
            curve[use] = chapman_richards(start[use], dt, a, fit["k"], fit["c"])
            median[use] = start[use] + median_growth
            scopes[scope] = scopes.get(scope, 0) + int(use.sum())
    if not all(np.isfinite(values).all() for values in (curve, median, fold_a)):
        raise ValueError("Some held-out cells lack growth predictions")
    return {
        "blocks": block_ids,
        "folds": folds,
        "curve": curve,
        "median": median,
        "A": fold_a,
        "literature_fallback": literature_fallback,
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
