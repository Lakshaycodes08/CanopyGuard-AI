from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.coreg import (
    accept,
    align,
    align_pooled,
    apply_shift,
    estimate_pooled_shift,
    estimate_shift,
)
from canopyguard.lidar.raster import shift_bilinear

RESOLUTION = 2.0


def rough_terrain(size: int = 160, seed: int = 0) -> np.ndarray:
    """A tilted surface with smooth relief, so aspect varies across the grid."""
    rng = np.random.default_rng(seed)
    row = np.arange(size, dtype=np.float64).reshape(-1, 1)
    column = np.arange(size, dtype=np.float64).reshape(1, -1)
    surface = 0.30 * column + 0.18 * row
    for _ in range(14):
        center_row, center_column = rng.uniform(0, size, size=2)
        width = rng.uniform(12.0, 30.0)
        surface = surface + rng.uniform(-14.0, 14.0) * np.exp(
            -((row - center_row) ** 2 + (column - center_column) ** 2) / (2 * width**2)
        )
    return surface


def offset_copy(surface: np.ndarray, dx: float, dy: float, dz: float) -> np.ndarray:
    return shift_bilinear(surface, dx, dy, RESOLUTION) + dz


@pytest.mark.parametrize(
    ("dx", "dy", "dz"),
    [(1.4, -0.9, 0.25), (-2.2, 1.7, -0.4), (0.6, 0.6, 0.0)],
)
def test_alignment_recovers_a_known_offset(dx, dy, dz):
    reference = rough_terrain()
    moving = offset_copy(reference, dx, dy, dz)
    result = align(reference, moving, RESOLUTION)
    assert result["dx_m"] == pytest.approx(dx, abs=0.12)
    assert result["dy_m"] == pytest.approx(dy, abs=0.12)
    assert result["dz_m"] == pytest.approx(dz, abs=0.12)
    assert result["converged"] == 1.0


def test_alignment_reduces_the_elevation_residual():
    reference = rough_terrain(seed=1)
    moving = offset_copy(reference, 1.8, -1.1, 0.3)
    result = align(reference, moving, RESOLUTION)
    assert result["rmse_after_m"] < 0.3 * result["rmse_before_m"]


def test_identical_grids_need_no_shift():
    reference = rough_terrain(seed=2)
    result = align(reference, reference.copy(), RESOLUTION)
    assert result["magnitude_m"] < 0.02
    assert result["converged"] == 1.0


def test_apply_shift_moves_the_grid_back_onto_the_reference():
    reference = rough_terrain(seed=3)
    moving = offset_copy(reference, 2.0, 0.0, 0.0)
    shift = estimate_shift(reference, moving, RESOLUTION)
    corrected = apply_shift(moving, shift, RESOLUTION)
    interior = slice(20, -20)
    residual = corrected[interior, interior] - reference[interior, interior]
    assert np.nanmax(np.abs(residual)) < 0.6


def test_flat_terrain_carries_no_horizontal_information():
    flat = np.zeros((60, 60))
    with pytest.raises(ValueError, match="Too few usable cells"):
        estimate_shift(flat, flat + 1.0, RESOLUTION)


def test_estimate_rejects_mismatched_grids():
    with pytest.raises(ValueError, match="same shape"):
        estimate_shift(np.zeros((4, 4)), np.zeros((4, 5)), RESOLUTION)


def test_estimate_rejects_an_inverted_slope_band():
    reference = rough_terrain(seed=4)
    with pytest.raises(ValueError, match="min_slope_deg < max_slope_deg"):
        estimate_shift(
            reference, reference, RESOLUTION, min_slope_deg=40.0, max_slope_deg=5.0
        )


def test_accept_applies_the_magnitude_limit():
    converged = {"converged": 1.0, "magnitude_m": 1.2}
    assert accept(converged, 1.5)
    assert not accept(converged, 1.0)
    assert not accept({"converged": 0.0, "magnitude_m": 0.1}, 1.5)


def test_pooled_shift_is_solved_from_every_tile():
    """A tile a few hundred metres across spans too narrow a range of aspect
    to resolve an offset alone, and the offset belongs to the epoch pair."""
    tiles = [rough_terrain(size=40, seed=seed) for seed in range(6)]
    pairs = [(tile, offset_copy(tile, 1.5, -0.8, 0.0)) for tile in tiles]
    pooled = estimate_pooled_shift(pairs, RESOLUTION)
    single = estimate_pooled_shift(pairs[:1], RESOLUTION)
    assert pooled["cells"] > single["cells"]
    assert pooled["dx_m"] == pytest.approx(1.5, abs=0.5)
    assert pooled["dy_m"] == pytest.approx(-0.8, abs=0.5)


def test_pooled_alignment_recovers_a_known_offset():
    tiles = [rough_terrain(size=60, seed=seed) for seed in range(4)]
    pairs = [(tile, offset_copy(tile, 2.0, 1.0, 0.0)) for tile in tiles]
    result = align_pooled(pairs, RESOLUTION)
    assert result["dx_m"] == pytest.approx(2.0, abs=0.3)
    assert result["dy_m"] == pytest.approx(1.0, abs=0.3)
    assert result["tiles"] == 4.0
    assert result["rmse_after_m"] < result["rmse_before_m"]


def test_pooled_alignment_needs_a_pair():
    with pytest.raises(ValueError, match="At least one grid pair"):
        align_pooled([], RESOLUTION)


def test_pooled_alignment_ignores_a_tile_without_usable_slope():
    flat = np.zeros((40, 40))
    tile = rough_terrain(size=40, seed=11)
    pairs = [(flat, flat + 1.0), (tile, offset_copy(tile, 1.0, 0.0, 0.0))]
    assert estimate_pooled_shift(pairs, RESOLUTION)["dx_m"] == pytest.approx(
        1.0, abs=0.5
    )


def test_pooled_alignment_needs_usable_cells():
    flat = np.zeros((40, 40))
    with pytest.raises(ValueError, match="Too few usable cells"):
        estimate_pooled_shift([(flat, flat + 1.0)], RESOLUTION)
