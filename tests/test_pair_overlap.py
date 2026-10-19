from __future__ import annotations

import pytest

from canopyguard.lidar import pair_overlap

CRS = "EPSG:32610"
LEFT = [(-122.30, 38.70, -122.20, 38.80)]
RIGHT = [(-122.25, 38.75, -122.10, 38.90)]
STUDY = (-122.90, 38.475, -122.74, 38.82)


def test_overlap_summary_measures_shared_area_and_distance() -> None:
    summary = pair_overlap.overlap_summary(LEFT, RIGHT, STUDY, CRS, [5, 50])

    # 0.05 deg by 0.05 deg at 38.75 N is about 4.3 km by 5.6 km.
    assert summary["shared_km2"] == pytest.approx(24.1, rel=0.05)
    assert summary["shared_in_study_box_km2"] == pytest.approx(0.0)
    assert summary["shared_distance_to_study_box_km"] == pytest.approx(42.0, rel=0.05)
    assert summary["shared_within_buffer_km2"]["5"] == pytest.approx(0.0)
    assert summary["shared_within_buffer_km2"]["50"] == pytest.approx(
        summary["shared_km2"]
    )
    assert len(summary["shared_patches"]) == 1


def test_shared_area_inside_the_box_is_counted() -> None:
    inside = [(-122.85, 38.60, -122.80, 38.65)]
    summary = pair_overlap.overlap_summary(inside, inside, STUDY, CRS, [5])

    assert summary["shared_in_study_box_km2"] == pytest.approx(summary["shared_km2"])
    assert summary["shared_distance_to_study_box_km"] == pytest.approx(0.0)


def test_patches_are_sorted_largest_first() -> None:
    first = [(0.0, 0.0, 0.1, 0.1), (1.0, 1.0, 1.02, 1.02)]
    summary = pair_overlap.overlap_summary(first, first, STUDY, CRS, [])

    sizes = [patch["km2"] for patch in summary["shared_patches"]]
    assert sizes == sorted(sizes, reverse=True)
    assert len(sizes) == 2


def test_disjoint_acquisitions_share_nothing() -> None:
    summary = pair_overlap.overlap_summary(
        [(0, 0, 1, 1)], [(5, 5, 6, 6)], STUDY, CRS, []
    )

    assert summary["shared_km2"] == 0.0
    with pytest.raises(ValueError, match="share no ground"):
        pair_overlap.shared_region([(0, 0, 1, 1)], [(5, 5, 6, 6)], 0.01)


def test_shared_tiles_lie_wholly_inside_both_footprints() -> None:
    tiles, region = pair_overlap.shared_tiles(LEFT, RIGHT, 500, 5, 0.005)

    assert tiles
    for west, south, east, north in tiles:
        assert west >= -122.25 and east <= -122.20
        assert south >= 38.75 and north <= 38.80
    assert region[0] < -122.25
