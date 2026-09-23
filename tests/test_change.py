from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.change import (
    bare_floor,
    bare_mask,
    baseline_years,
    canopy_mask,
    canopy_stratum,
    change_row,
    disturbance,
    disturbed_mask,
    pair_epochs,
    surface_table,
)

MEASURED = {
    "lod95_m": {10: 0.235, 20: 0.210, 30: 0.199, 50: 0.199},
    "sigma_reference_m": 0.092,
    "decay_exponent": 0.054,
}
FIRST = np.array([[0.2, 0.5, 10.0], [20.0, np.nan, 1.5]])
SECOND = np.array([[0.4, 3.0, 11.0], [12.0, 5.0, 0.3]])


def test_baseline_is_measured_between_start_dates():
    assert baseline_years("2013-09-28", "2022-09-13") == pytest.approx(8.96, abs=0.01)
    with pytest.raises(ValueError, match="start after"):
        baseline_years("2022-09-13", "2013-09-28")


def test_pair_epochs_are_found_by_name():
    config = {"epochs": [{"name": "2013"}, {"name": "2022"}]}
    first, second = pair_epochs(config, ("2013", "2022"))
    assert (first["name"], second["name"]) == ("2013", "2022")
    with pytest.raises(ValueError, match="No epoch named: 2030"):
        pair_epochs(config, ("2013", "2030"))


def test_bare_cells_are_low_in_both_epochs():
    mask = bare_mask(FIRST, SECOND, 1.0)
    assert mask.tolist() == [[True, False, False], [False, False, False]]


def test_canopy_cells_use_the_mean_of_both_epochs():
    mask = canopy_mask(FIRST, SECOND, 2.0)
    assert mask.tolist() == [[False, False, True], [True, False, False]]


def test_disturbed_cells_change_beyond_the_limit_either_way():
    mask = disturbed_mask(FIRST, SECOND, 3.0)
    assert mask.tolist() == [[False, False, False], [True, False, False]]
    with pytest.raises(ValueError, match="must be positive"):
        disturbed_mask(FIRST, SECOND, 0.0)


def test_canopy_stratum_drops_disturbed_canopy():
    first, second = canopy_stratum(FIRST, SECOND, 2.0, 3.0)
    assert np.isfinite(first).tolist() == [[False, False, True], [False, False, False]]
    assert second[0, 2] == 11.0


def test_masks_reject_mismatched_grids():
    with pytest.raises(ValueError, match="share a grid"):
        bare_mask(np.zeros((2, 2)), np.zeros((3, 3)), 1.0)


def test_bare_floor_reports_bias_and_spread():
    rng = np.random.default_rng(0)
    change = rng.normal(0.1, 0.2, size=(200, 200))
    bare = np.ones_like(change, dtype=bool)
    bare[:, :100] = False
    change[:, :100] = 50.0
    floor = bare_floor(change, bare)
    assert floor["cells"] == 20000.0
    assert floor["mean_m"] == pytest.approx(0.1, abs=0.01)
    assert floor["nmad_m"] == pytest.approx(0.2, abs=0.01)


def test_bare_floor_without_bare_cells_is_empty():
    floor = bare_floor(np.ones((3, 3)), np.zeros((3, 3), dtype=bool))
    assert floor["cells"] == 0.0
    assert np.isnan(floor["nmad_m"])


def test_disturbance_counts_loss_and_gain_separately():
    change = np.array([-5.0, -1.0, 0.0, 1.0, 4.0, 6.0, np.nan, -3.0])
    result = disturbance(change, 3.0)
    assert result["valid_cells"] == 7.0
    assert result["loss_fraction"] == pytest.approx(1 / 7)
    assert result["gain_fraction"] == pytest.approx(2 / 7)


def test_change_row_carries_the_signed_median():
    delta = np.array([-2.0, -1.0, -0.5, 0.1, np.nan])
    row = change_row(delta, 0.1, 10.0, 9.0, min_cells=3)
    assert row["median_change_m"] == pytest.approx(-0.75)
    assert row["signal_m"] == pytest.approx(0.75)
    assert row["cells"] == 4.0
    assert row["admitted"] is True
    assert row["detectable_fraction"] == pytest.approx(0.75)


def test_change_row_with_too_few_cells_is_not_admitted():
    row = change_row(np.array([np.nan, 1.0]), 0.1, 200.0, 9.0)
    assert row["cells"] == 1.0
    assert row["admitted"] is False
    assert np.isnan(row["median_change_m"])


def test_surface_table_uses_the_measured_floor():
    rng = np.random.default_rng(1)
    all_cells = {10.0: rng.normal(0.5, 1.0, 400), 100.0: rng.normal(0.5, 0.2, 4)}
    canopy = {10.0: rng.normal(1.0, 1.0, 300), 100.0: np.array([np.nan])}
    table = surface_table(all_cells, canopy, MEASURED, 9.0, min_cells=200)
    assert [row["scale_m"] for row in table] == [10.0, 100.0]
    assert table[0]["lod95_m"] == pytest.approx(0.235)
    assert table[0]["all"]["sigma_m"] == pytest.approx(0.235 / 1.96)
    assert table[1]["lod95_m"] == pytest.approx(0.092 * 1.96)
    assert table[0]["canopy"]["admitted"] is True
    assert table[1]["all"]["admitted"] is False
    assert table[1]["canopy"]["cells"] == 0.0
