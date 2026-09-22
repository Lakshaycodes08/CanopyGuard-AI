from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.detectability import (
    decay_exponent,
    detectable_fraction,
    lod95,
    minimum_detectable_baseline,
    noise_sigma,
    normalised_mad,
    smallest_resolving_scale,
    surface_row,
)


def test_normalised_mad_matches_sigma_for_gaussian_noise():
    noise = np.random.default_rng(0).normal(scale=2.0, size=20000)
    assert normalised_mad(noise) == pytest.approx(2.0, rel=0.05)


def test_robust_sigma_resists_outliers_that_break_the_plain_estimate():
    rng = np.random.default_rng(1)
    clean = rng.normal(scale=1.0, size=5000)
    contaminated = np.concatenate([clean, np.full(100, 80.0)])
    assert noise_sigma(contaminated, robust=True) == pytest.approx(1.0, rel=0.1)
    assert noise_sigma(contaminated, robust=False) > 5.0


def test_lod95_is_the_two_sided_ninety_five_percent_bound():
    assert lod95(1.0) == pytest.approx(1.96)
    with pytest.raises(ValueError, match="non-negative"):
        lod95(-0.1)


def test_independent_error_gives_a_half_power_decay():
    """Averaging N independent cells reduces sigma as N to the minus one half."""
    scales = np.array([10.0, 20.0, 50.0, 100.0, 200.0])
    cells = (scales / 10.0) ** 2
    sigma = 4.0 * cells**-0.5
    fit = decay_exponent(scales, sigma, base_scale_m=10.0)
    assert fit["exponent"] == pytest.approx(0.5, abs=1e-6)
    assert fit["coefficient"] == pytest.approx(4.0, rel=1e-6)


def test_correlated_error_gives_an_exponent_below_one_half():
    scales = np.array([10.0, 20.0, 50.0, 100.0, 200.0])
    cells = (scales / 10.0) ** 2
    sigma = 4.0 * cells**-0.15
    fit = decay_exponent(scales, sigma, base_scale_m=10.0)
    assert fit["exponent"] < 0.5
    assert fit["exponent"] == pytest.approx(0.15, abs=1e-6)


def test_decay_fit_requires_three_scales():
    with pytest.raises(ValueError, match="at least three scales"):
        decay_exponent([10.0, 20.0], [1.0, 0.5], base_scale_m=10.0)


def test_detectable_fraction_counts_only_changes_above_the_limit():
    delta = np.array([0.1, 0.5, 3.0, -4.0, 0.0])
    assert detectable_fraction(delta, limit=1.0) == pytest.approx(0.4)


def test_surface_row_reports_snr_and_annual_rate():
    rng = np.random.default_rng(2)
    delta = rng.normal(loc=3.0, scale=0.2, size=4000)
    row = surface_row(delta, sigma=1.0, scale_m=100.0, baseline_years=9.0)
    assert row["snr"] == pytest.approx(3.0, rel=0.05)
    assert row["annual_rate_m"] == pytest.approx(1.0 / 3.0, rel=0.05)
    assert row["lod95_m"] == pytest.approx(1.96)
    assert row["detectable_fraction"] == pytest.approx(1.0)


def test_one_year_signal_below_the_floor_is_not_detectable():
    """The blocked design: annual growth against a metre-scale noise floor."""
    rng = np.random.default_rng(3)
    delta = rng.normal(loc=0.3, scale=2.0, size=5000)
    row = surface_row(delta, sigma=2.0, scale_m=10.0, baseline_years=1.0)
    assert row["snr"] < 1.0


def test_minimum_detectable_baseline_scales_with_growth_rate():
    assert minimum_detectable_baseline(1.0, 0.61) == pytest.approx(1.96 / 0.61)
    assert minimum_detectable_baseline(1.0, 0.075) > 25.0
    with pytest.raises(ValueError, match="must be positive"):
        minimum_detectable_baseline(1.0, 0.0)


def test_smallest_resolving_scale_picks_the_first_scale_clearing_snr_one():
    rows = [
        {"scale_m": 10.0, "snr": 0.4},
        {"scale_m": 100.0, "snr": 0.9},
        {"scale_m": 500.0, "snr": 1.3},
        {"scale_m": 1000.0, "snr": 2.1},
    ]
    assert smallest_resolving_scale(rows) == 500.0
    assert np.isnan(smallest_resolving_scale(rows, min_snr=9.0))
