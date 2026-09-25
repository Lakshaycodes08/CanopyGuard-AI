from __future__ import annotations

import pytest

from canopyguard.lidar.footprint import (
    area_km2,
    as_box,
    covered_area_km2,
    intersect,
    intersect_all,
    probe_grid,
    stratum_shortfall,
)

STUDY = (-122.90, 38.475, -122.74, 38.82)
B22 = (-123.534997, 38.097176, -122.353713, 38.930173)
B23 = (-123.391815, 38.142903, -122.053325, 39.416429)


def test_as_box_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="west < east"):
        as_box(1.0, 0.0, 0.0, 1.0)


def test_study_area_sits_inside_both_recent_epochs():
    assert intersect(STUDY, B22) == STUDY
    assert intersect(STUDY, B23) == STUDY


def test_disjoint_boxes_do_not_intersect():
    assert intersect(STUDY, (0.0, 0.0, 1.0, 1.0)) is None


def test_intersect_all_narrows_to_the_common_overlap():
    common = intersect_all([B22, B23])
    assert common is not None
    assert common[3] == pytest.approx(B22[3])
    assert common[0] == pytest.approx(B23[0])


def test_intersect_all_returns_none_when_any_box_is_disjoint():
    assert intersect_all([B22, B23, (0.0, 0.0, 1.0, 1.0)]) is None


def test_study_area_is_about_five_hundred_square_kilometres():
    assert area_km2(STUDY) == pytest.approx(530.0, rel=0.05)


def test_probe_grid_tiles_the_box_without_loss():
    probes = probe_grid(STUDY, rows=4, columns=2)
    assert len(probes) == 8
    tiled = sum(area_km2(box) for box in probes)
    assert tiled == pytest.approx(area_km2(STUDY), rel=1e-4)


def test_probe_grid_rejects_an_empty_grid():
    with pytest.raises(ValueError, match="at least one row"):
        probe_grid(STUDY, 0, 2)


def test_covered_area_counts_only_probes_where_the_epoch_was_found():
    probes = probe_grid(STUDY, rows=4, columns=1)
    present = [False, False, False, True]
    assert covered_area_km2(probes, present) == pytest.approx(area_km2(probes[3]))


def test_covered_area_rejects_mismatched_lists():
    with pytest.raises(ValueError, match="same length"):
        covered_area_km2(probe_grid(STUDY, 2, 1), [True])


def test_stratum_shortfall_names_the_thin_strata():
    counts = {"conifer_steep": 500, "conifer_gentle": 9000, "oak_steep": 1200}
    assert stratum_shortfall(counts, 2000) == {"conifer_steep": 500, "oak_steep": 1200}
    assert stratum_shortfall(counts, 100) == {}
