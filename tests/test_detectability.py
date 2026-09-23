from __future__ import annotations

import numpy as np
import pytest

from canopyguard.evaluation.detectability import (
    decay_exponent,
    detectable_fraction,
    lod95,
    lod95_at,
    minimum_detectable_baseline,
    noise_floor_table,
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


def test_noise_floor_table_reports_every_scale_and_the_decay():
    rng = np.random.default_rng(7)
    base = 10.0
    scales = [10.0, 20.0, 50.0, 100.0]
    ladder = {}
    for scale in scales:
        cells = (scale / base) ** 2
        ladder[scale] = rng.normal(scale=3.0 * cells**-0.25, size=4000)

    rows = noise_floor_table(ladder, base_scale_m=base)
    assert [row["scale_m"] for row in rows] == scales
    assert rows[0]["sigma_m"] > rows[-1]["sigma_m"]
    assert rows[0]["lod95_m"] == pytest.approx(1.96 * rows[0]["sigma_m"])
    assert rows[0]["decay_exponent"] == pytest.approx(0.25, abs=0.05)


def test_noise_floor_table_carries_the_same_decay_to_every_row():
    ladder = {s: np.random.default_rng(1).normal(size=500) for s in (10.0, 20.0, 40.0)}
    rows = noise_floor_table(ladder, base_scale_m=10.0)
    assert len({row["decay_exponent"] for row in rows}) == 1


def test_a_scale_below_the_cell_minimum_is_reported_but_not_admitted():
    """A spread from a handful of cells carries no information, so it does
    not enter the gate or the decay fit."""
    generator = np.random.default_rng(3)
    ladder = {
        10.0: generator.normal(0.0, 1.0, 4000),
        20.0: generator.normal(0.0, 0.7, 1000),
        50.0: generator.normal(0.0, 0.5, 400),
        200.0: generator.normal(0.0, 3.0, 4),
    }
    rows = noise_floor_table(ladder, base_scale_m=10.0, min_cells=200)
    admitted = {row["scale_m"]: row["admitted"] for row in rows}
    assert admitted == {10.0: True, 20.0: True, 50.0: True, 200.0: False}
    assert rows[0]["decay_scales"] == 3.0
    assert rows[0]["decay_exponent"] > 0.0


def test_decay_is_not_fitted_below_three_admitted_scales():
    generator = np.random.default_rng(4)
    ladder = {10.0: generator.normal(0.0, 1.0, 400), 20.0: generator.normal(0, 1, 4)}
    rows = noise_floor_table(ladder, base_scale_m=10.0, min_cells=200)
    assert np.isnan(rows[0]["decay_exponent"])


def test_relative_error_falls_with_the_cell_count():
    generator = np.random.default_rng(5)
    ladder = {10.0: generator.normal(0, 1, 5000), 20.0: generator.normal(0, 1, 50)}
    rows = noise_floor_table(ladder, base_scale_m=10.0)
    assert rows[0]["sigma_relative_error"] < rows[1]["sigma_relative_error"]


def test_both_spread_estimates_are_reported():
    generator = np.random.default_rng(6)
    rows = noise_floor_table({10.0: generator.normal(0, 1, 2000)}, base_scale_m=10.0)
    assert rows[0]["sigma_m"] == pytest.approx(1.0, abs=0.1)
    assert rows[0]["sigma_plain_m"] == pytest.approx(1.0, abs=0.1)


def test_lod95_at_returns_the_measured_value_for_an_admitted_scale():
    measured = {
        "lod95_m": {10: 0.235, 20: 0.210, 30: 0.199, 50: 0.199},
        "sigma_reference_m": 0.092,
        "decay_exponent": 0.054,
    }
    assert lod95_at(30, measured) == pytest.approx(0.199)


def test_lod95_at_extrapolates_for_an_unadmitted_scale():
    measured = {
        "lod95_m": {10: 0.235, 20: 0.210, 30: 0.199, 50: 0.199},
        "sigma_reference_m": 0.092,
        "decay_exponent": 0.054,
    }
    assert lod95_at(100, measured) == pytest.approx(lod95(0.092))
    expected_200 = lod95(0.092 * (200.0 / 100.0) ** (-2.0 * 0.054))
    assert lod95_at(200, measured) == pytest.approx(expected_200)
