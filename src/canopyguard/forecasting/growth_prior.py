"""Type-specific median height increments for the stage-one growth prior."""

from __future__ import annotations

import numpy as np


def training_scope(
    model_group: str,
    broad_group: str,
    train: np.ndarray,
    groups: np.ndarray,
    broad: np.ndarray,
    minimum: int,
) -> tuple[str, np.ndarray]:
    """Use a mapped type when large enough, otherwise its broad forest group."""
    own = train & (groups == model_group)
    if not model_group.startswith("group:") and own.sum() >= minimum:
        return "type:" + model_group, own
    pooled = train & (broad == broad_group)
    if pooled.sum() < minimum:
        raise ValueError(f"Too few training cells for broad group {broad_group}")
    return "broad:" + broad_group, pooled


def fit_type_median_prior(frame, start, end, minimum: int) -> dict[str, dict]:
    """Fit one median 2013-2022 increment per map class or pooled group."""
    x = np.asarray(start, dtype=float)
    y = np.asarray(end, dtype=float)
    if len(frame) != len(x) or len(x) != len(y):
        raise ValueError("Frame and height arrays must have equal length")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Median prior requires finite heights")
    groups = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    names = frame["vegetation_type"].to_numpy()
    train = np.ones(len(frame), dtype=bool)
    output = {}
    for name in np.unique(names):
        first = np.flatnonzero(names == name)[0]
        scope, rows = training_scope(
            groups[first], broad[first], train, groups, broad, minimum
        )
        output[name] = {
            "fit_scope": scope,
            "training_cells": int(rows.sum()),
            "median_increment_m": float(np.median(y[rows] - x[rows])),
        }
    return output


def predict_type_median_prior(names, start, prior: dict[str, dict]) -> np.ndarray:
    """Apply a trained map-class increment to starting canopy height."""
    labels = np.asarray(names)
    height = np.asarray(start, dtype=float)
    if len(labels) != len(height) or not np.isfinite(height).all():
        raise ValueError("Names and finite starting heights must align")
    missing = sorted(set(labels) - prior.keys())
    if missing:
        raise ValueError(f"No growth prior for: {', '.join(missing)}")
    increment = np.array([prior[name]["median_increment_m"] for name in labels])
    return height + increment
