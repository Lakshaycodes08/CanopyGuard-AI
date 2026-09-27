from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.blocks import (
    assign_blocks,
    empirical_variogram,
    fit_spherical,
    practical_range,
    select_block_size,
    spherical_model,
    systematic_folds,
)


def _grid(side: int, spacing: float = 100.0):
    axis = np.arange(side, dtype=np.float64) * spacing
    x, y = np.meshgrid(axis, axis)
    return x.ravel(), y.ravel()


def test_assign_blocks_groups_by_edge_length():
    x, y = _grid(4)
    blocks = assign_blocks(x, y, block_size_m=200.0)
    assert np.unique(blocks).size == 4
    assert np.bincount(blocks - blocks.min()).max() == 4


def test_assign_blocks_rejects_non_positive_size():
    with pytest.raises(ValueError, match="must be positive"):
        assign_blocks([0.0], [0.0], 0.0)


def test_folds_are_balanced_and_dispersed():
    x, y = _grid(10)
    blocks = assign_blocks(x, y, block_size_m=100.0)
    folds = systematic_folds(blocks, n_folds=5, seed=1)
    counts = np.bincount(folds)
    assert counts.size == 5
    assert counts.max() - counts.min() <= len(np.unique(blocks)) % 5 + 1
    assert np.all(folds[blocks == blocks[0]] == folds[blocks == blocks[0]][0])


def test_folds_reject_more_folds_than_blocks():
    with pytest.raises(ValueError, match="cannot exceed"):
        systematic_folds([0, 0, 1], n_folds=5)


def test_spherical_model_saturates_beyond_the_range():
    values = spherical_model([0.0, 250.0, 500.0, 900.0], 0.2, 1.0, 500.0)
    assert values[0] == pytest.approx(0.2)
    assert values[-1] == pytest.approx(1.2)
    assert np.all(np.diff(values) >= 0)


def test_variogram_recovers_a_known_correlation_range():
    rng = np.random.default_rng(0)
    side, spacing, true_range = 40, 50.0, 400.0
    x, y = _grid(side, spacing)
    centres = rng.uniform(0.0, side * spacing, size=(60, 2))
    amplitude = rng.normal(size=centres.shape[0])
    field = np.zeros_like(x)
    for (cx, cy), weight in zip(centres, amplitude, strict=True):
        field += weight * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * true_range**2))

    lags, gamma, counts = empirical_variogram(
        x, y, field, lag_m=50.0, max_distance_m=1500.0, max_pairs=200_000
    )
    assert counts.sum() > 0
    fit = fit_spherical(lags, gamma, counts)
    assert fit["sill"] > 0
    assert fit["nugget"] < 0.2 * fit["sill"]
    assert 400.0 < practical_range(fit) < 1600.0


def test_variogram_of_white_noise_is_flat():
    rng = np.random.default_rng(1)
    x, y = _grid(30)
    noise = rng.normal(size=x.size)
    lags, gamma, counts = empirical_variogram(
        x, y, noise, lag_m=100.0, max_distance_m=1200.0, max_pairs=200_000
    )
    populated = counts > 0
    spread = np.nanstd(gamma[populated]) / np.nanmean(gamma[populated])
    assert spread < 0.15


def test_variogram_rejects_bad_lag_settings():
    with pytest.raises(ValueError, match="0 < lag_m"):
        empirical_variogram([0.0, 1.0], [0.0, 1.0], [0.0, 1.0], 100.0, 50.0)


def test_block_size_selection_takes_the_smallest_admissible_candidate():
    assert select_block_size(640.0, [500.0, 1000.0, 2000.0], 500.0) == 1000.0
    assert select_block_size(120.0, [500.0, 1000.0], 500.0) == 500.0
    assert select_block_size(9000.0, [500.0, 1000.0], 500.0) == 1000.0
