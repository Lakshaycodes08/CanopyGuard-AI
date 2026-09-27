from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.noise_floor import (
    admit_tile,
    canopy_height,
    complete_tiles,
    evaluate_gate,
    height_summary,
    pool_ladder,
    stable_heights,
    surface_paths,
    tile_stem,
)

CONFIG = {"chm": {"clamp_min_m": 0.0, "clamp_max_m": 120.0}}
GATE = {
    "max_mean_one_year_change_m": 1.5,
    "max_shift_m": 1.5,
    "sigma_reference_scale_m": 100,
    "max_sigma_at_reference_m": 2.0,
}


def rows(sigma_100: float, mean_fine: float = 0.3):
    return [
        {"scale_m": 10.0, "sigma_m": 3.0, "lod95_m": 5.88, "mean_m": mean_fine},
        {
            "scale_m": 100.0,
            "sigma_m": sigma_100,
            "lod95_m": sigma_100 * 1.96,
            "mean_m": mean_fine,
        },
    ]


def test_canopy_height_is_surface_minus_terrain():
    chm = canopy_height(np.array([[110.0]]), np.array([[100.0]]), CONFIG)
    assert chm[0, 0] == pytest.approx(10.0)


def test_canopy_height_clamps_impossible_values():
    chm = canopy_height(np.array([[95.0, 400.0]]), np.array([[100.0, 100.0]]), CONFIG)
    assert np.isnan(chm[0, 0])
    assert np.isnan(chm[0, 1])


def test_canopy_height_rejects_mismatched_grids():
    with pytest.raises(ValueError, match="share a grid"):
        canopy_height(np.zeros((2, 2)), np.zeros((3, 3)), CONFIG)


def test_tile_stem_is_zero_padded():
    assert tile_stem("2022", 7) == "2022_t0007"


def test_surface_paths_cover_the_three_products(tmp_path):
    paths = surface_paths(tmp_path, "2023", 3)
    assert set(paths) == {"dtm", "dsm", "chm"}
    assert paths["dtm"].name == "dtm_2023_t0003.tif"


def test_complete_tiles_requires_both_epochs(tmp_path):
    plan = {"tiles": [{"index": 0}, {"index": 1}]}
    for kind in ("dtm", "dsm"):
        for epoch in ("2022", "2023"):
            surface_paths(tmp_path, epoch, 0)[kind].write_bytes(b"x")
    surface_paths(tmp_path, "2022", 1)["dtm"].write_bytes(b"x")
    assert complete_tiles(plan, tmp_path, ("2022", "2023")) == [0]


def test_pool_ladder_concatenates_per_scale():
    deltas = [
        {10.0: np.array([[1.0, 2.0]]), 100.0: np.array([[3.0]])},
        {10.0: np.array([[4.0]]), 100.0: np.array([[5.0]])},
    ]
    pooled = pool_ladder(deltas)
    assert pooled[10.0].tolist() == [1.0, 2.0, 4.0]
    assert pooled[100.0].tolist() == [3.0, 5.0]


def test_pool_ladder_rejects_an_empty_run():
    with pytest.raises(ValueError, match="No tile produced"):
        pool_ladder([])


def shift(magnitude_m: float = 0.4, converged: float = 1.0, tiles: float = 5.0):
    return {"magnitude_m": magnitude_m, "converged": converged, "tiles": tiles}


def test_gate_passes_a_clean_result():
    result = evaluate_gate(rows(1.2), shift(), GATE)
    assert result["passed"]
    assert result["tiles"] == 5.0


def test_gate_fails_on_a_high_sigma_at_the_reference_scale():
    result = evaluate_gate(rows(2.6), shift(), GATE)
    assert not result["passed"]
    assert not result["checks"]["sigma_at_reference_below_limit"]


def test_gate_fails_on_an_implausible_mean_change():
    result = evaluate_gate(rows(1.0, mean_fine=-6.0), shift(), GATE)
    assert not result["checks"]["mean_one_year_change_in_range"]


def test_gate_accepts_a_negative_mean_inside_the_detection_limit():
    result = evaluate_gate(rows(1.0, mean_fine=-2.0), shift(), GATE)
    assert result["checks"]["mean_one_year_change_in_range"]


def test_gate_tolerates_a_rise_inside_the_sampling_error():
    rows_ = [
        {
            "scale_m": 30.0,
            "sigma_m": 0.104,
            "mean_m": 0.0,
            "sigma_relative_error": 0.020,
        },
        {
            "scale_m": 50.0,
            "sigma_m": 0.109,
            "mean_m": 0.0,
            "sigma_relative_error": 0.032,
        },
    ]
    assert evaluate_gate(rows_, shift(), GATE)["checks"]["sigma_falls_with_scale"]


def test_stable_heights_blank_disturbed_cells_in_both_epochs():
    first = np.array([[10.0, 20.0, np.nan]])
    second = np.array([[10.5, 5.0, 3.0]])
    a, b, counts = stable_heights(first, second, 3.0)
    assert a[0, 0] == 10.0 and b[0, 0] == 10.5
    assert np.isnan(a[0, 1]) and np.isnan(b[0, 1])
    assert counts == (1, 2)


def test_stable_heights_reject_a_non_positive_limit():
    with pytest.raises(ValueError, match="must be positive"):
        stable_heights(np.zeros((1, 1)), np.zeros((1, 1)), 0.0)


def test_gate_fails_on_a_large_coregistration_shift():
    result = evaluate_gate(rows(1.0), shift(magnitude_m=3.0), GATE)
    assert not result["checks"]["shift_below_limit"]


def test_gate_fails_when_the_solver_did_not_converge():
    result = evaluate_gate(rows(1.0), shift(converged=0.0), GATE)
    assert not result["checks"]["coregistration_converged"]


def test_gate_fails_when_sigma_rises_with_scale():
    bad = [
        {"scale_m": 10.0, "sigma_m": 1.0, "mean_m": 0.3},
        {"scale_m": 100.0, "sigma_m": 1.5, "mean_m": 0.3},
    ]
    assert not evaluate_gate(bad, shift(), GATE)["checks"]["sigma_falls_with_scale"]


def test_gate_needs_a_measured_scale():
    with pytest.raises(ValueError, match="at least one measured scale"):
        evaluate_gate([], shift(), GATE)


ADMISSION = {"min_valid_fraction": 0.5, "min_coverage_agreement": 0.8}


def surface(valid_cells: int, size: int = 100):
    grid = np.full(size, np.nan)
    grid[:valid_cells] = 10.0
    return grid.reshape(10, 10)


def test_a_tile_both_epochs_cover_is_admitted():
    verdict = admit_tile(surface(90), surface(85), ADMISSION)
    assert verdict["admitted"]
    assert verdict["coverage_agreement"] == pytest.approx(85 / 90)


def test_an_empty_epoch_is_rejected():
    """The raster writer produces a file even when no point reaches it, so a
    tile outside one acquisition looks built."""
    verdict = admit_tile(surface(90), surface(0), ADMISSION)
    assert not verdict["admitted"]
    assert verdict["reason"] == "coverage below the minimum"


def test_epochs_that_disagree_on_coverage_are_rejected():
    """A tenth of the returns in one epoch lowers the surface maximum in that
    epoch alone, which reads as canopy loss."""
    verdict = admit_tile(surface(95), surface(55), ADMISSION)
    assert not verdict["admitted"]
    assert verdict["reason"] == "epoch coverages disagree"


def test_mismatched_grids_are_rejected():
    assert not admit_tile(np.zeros((4, 4)), np.zeros((5, 5)), ADMISSION)["admitted"]


def test_height_summary_describes_what_the_tile_carries():
    heights = np.array([[0.5, 1.0, 3.0, 8.0, 12.0, np.nan]])
    summary = height_summary(heights)
    assert summary["cells"] == 5.0
    assert summary["median_m"] == pytest.approx(3.0)
    assert summary["above_2m"] == pytest.approx(0.6)
    assert summary["above_10m"] == pytest.approx(0.2)


def test_height_summary_of_an_empty_tile():
    assert height_summary(np.full((3, 3), np.nan)) == {"cells": 0.0}


def test_gate_ignores_a_scale_the_sample_cannot_support():
    measured = rows(1.2) + [
        {"scale_m": 200.0, "sigma_m": 9.0, "mean_m": -3.0, "admitted": False}
    ]
    for row in measured[:2]:
        row["admitted"] = True
    result = evaluate_gate(measured, shift(), GATE)
    assert result["admitted_scales"] == [10.0, 100.0]
    assert result["passed"]


def test_gate_fails_when_the_reference_scale_cannot_be_reached():
    measured = [{"scale_m": 10.0, "sigma_m": 0.3, "mean_m": 0.3, "admitted": True}]
    result = evaluate_gate(measured, shift(), GATE)
    assert not result["checks"]["reference_sigma_available"]
    assert not result["passed"]


def test_gate_extrapolates_an_unsupported_reference_scale():
    decay = {
        "decay_coefficient": 1.0,
        "decay_exponent": 0.25,
        "decay_base_scale_m": 1.0,
        "admitted": True,
        "mean_m": 0.0,
    }
    measured = [
        {**decay, "scale_m": 10.0, "sigma_m": 0.32},
        {**decay, "scale_m": 20.0, "sigma_m": 0.22},
        {**decay, "scale_m": 50.0, "sigma_m": 0.14},
        {**decay, "scale_m": 100.0, "sigma_m": 0.5, "admitted": False},
    ]
    result = evaluate_gate(measured, shift(), GATE)
    assert result["reference_source"] == "extrapolated"
    assert result["reference_sigma_m"] == pytest.approx(0.1)
    assert result["passed"]


def test_gate_needs_an_admitted_scale():
    with pytest.raises(ValueError, match="at least one measured scale"):
        evaluate_gate(
            [{"scale_m": 10.0, "sigma_m": 1.0, "mean_m": 0.0, "admitted": False}],
            shift(),
            GATE,
        )
