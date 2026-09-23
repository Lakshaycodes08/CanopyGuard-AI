from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.noise_floor import (
    canopy_height,
    complete_tiles,
    evaluate_gate,
    pool_ladder,
    surface_paths,
    tile_stem,
)

CONFIG = {"chm": {"clamp_min_m": 0.0, "clamp_max_m": 120.0}}
GATE = {
    "mean_one_year_change_m": [0.0, 1.5],
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
    result = evaluate_gate(rows(1.0, mean_fine=-2.0), shift(), GATE)
    assert not result["checks"]["mean_one_year_change_in_range"]


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
