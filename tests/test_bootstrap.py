from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.bootstrap import excludes_zero, paired_block_bootstrap


def _blocked_errors(seed: int, shift: float, blocks: int = 40, per_block: int = 25):
    """Errors with a block-level offset, which is the spatial correlation."""
    rng = np.random.default_rng(seed)
    block_ids = np.repeat(np.arange(blocks), per_block)
    block_offset = rng.normal(scale=1.0, size=blocks)[block_ids]
    baseline = np.abs(block_offset + rng.normal(scale=0.2, size=block_ids.size)) + 1.0
    return baseline, baseline - shift, block_ids


def test_identical_models_give_an_interval_containing_zero():
    errors, _, block_ids = _blocked_errors(seed=0, shift=0.0)
    result = paired_block_bootstrap(errors, errors, block_ids, resamples=300)
    assert result["difference"] == pytest.approx(0.0)
    assert result["ci_low"] <= 0.0 <= result["ci_high"]
    assert not excludes_zero(result)


def test_a_clearly_better_model_excludes_zero():
    worse, better, block_ids = _blocked_errors(seed=1, shift=0.5)
    result = paired_block_bootstrap(worse, better, block_ids, resamples=300)
    assert result["difference"] == pytest.approx(0.5, abs=1e-9)
    assert excludes_zero(result)
    assert result["ci_low"] > 0.0


def test_block_resampling_is_wider_than_cell_resampling():
    """Treating correlated cells as independent understates the interval."""
    worse, better, block_ids = _blocked_errors(seed=2, shift=0.05)
    blocked = paired_block_bootstrap(worse, better, block_ids, resamples=400)
    per_cell = paired_block_bootstrap(
        worse, better, np.arange(block_ids.size), resamples=400
    )
    blocked_width = blocked["ci_high"] - blocked["ci_low"]
    cell_width = per_cell["ci_high"] - per_cell["ci_low"]
    assert blocked_width > cell_width


def test_result_is_deterministic_for_a_fixed_seed():
    worse, better, block_ids = _blocked_errors(seed=3, shift=0.2)
    first = paired_block_bootstrap(worse, better, block_ids, resamples=200, seed=7)
    second = paired_block_bootstrap(worse, better, block_ids, resamples=200, seed=7)
    assert first == second


def test_custom_statistic_is_honoured():
    worse, better, block_ids = _blocked_errors(seed=4, shift=0.3)
    result = paired_block_bootstrap(
        worse,
        better,
        block_ids,
        statistic=lambda values: float(np.sqrt(np.mean(values**2))),
        resamples=200,
    )
    assert result["difference"] > 0.0


def test_rejects_a_single_block():
    with pytest.raises(ValueError, match="at least two blocks"):
        paired_block_bootstrap([1.0, 2.0], [1.0, 2.0], [0, 0])


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same shape"):
        paired_block_bootstrap([1.0, 2.0], [1.0], [0, 1])
