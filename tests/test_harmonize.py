from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.harmonize import (
    admit_epoch,
    class_mask,
    decimation_target,
    poisson_radius,
    retained_fraction,
    scan_angle_mask,
)

SCREEN = {
    "min_density_pts_m2": 8.0,
    "leaf_on_months": [9, 10, 11, 12],
    "require_declared_vertical_datum": True,
}


def epoch(**overrides):
    base = {
        "name": "2022",
        "start": "2022-09-13",
        "end": "2022-11-11",
        "nominal_density_pts_m2": 21.51,
        "geoid": "GEOID18",
    }
    return {**base, **overrides}


def test_autumn_epoch_is_admitted():
    assert admit_epoch(epoch(), SCREEN)["admitted"]


def test_spring_epoch_fails_the_leaf_on_window():
    spring = epoch(name="2007", start="2007-03-21", end="2007-04-17")
    result = admit_epoch(spring, SCREEN)
    assert not result["admitted"]
    assert len(result["failures"]) == 2


def test_sparse_epoch_fails_the_density_floor():
    result = admit_epoch(epoch(nominal_density_pts_m2=4.0), SCREEN)
    assert not result["admitted"]
    assert "below" in result["failures"][0]


def test_missing_geoid_fails():
    result = admit_epoch(epoch(geoid=None), SCREEN)
    assert "geoid not declared" in result["failures"]


def test_unknown_density_fails():
    assert not admit_epoch(epoch(nominal_density_pts_m2=None), SCREEN)["admitted"]


def test_decimation_target_is_the_sparsest_epoch():
    assert decimation_target([21.51, 13.73, 21.32], 8.0) == pytest.approx(13.73)


def test_decimation_target_rejects_a_target_below_the_floor():
    with pytest.raises(ValueError, match="below the floor"):
        decimation_target([21.5, 4.0], 8.0)


def test_poisson_radius_matches_the_requested_density():
    assert poisson_radius(4.0) == pytest.approx(0.5)
    assert poisson_radius(13.73) == pytest.approx(1.0 / np.sqrt(13.73))


def test_scan_angle_mask_keeps_the_shared_band():
    angles = np.array([-20.0, -15.0, 0.0, 15.0, 20.0])
    assert scan_angle_mask(angles, 15.0).tolist() == [False, True, True, True, False]


def test_class_mask_drops_noise_and_water():
    classes = np.array([2, 5, 7, 9, 2])
    assert class_mask(classes, [7, 9]).tolist() == [True, True, False, False, True]


def test_retained_fraction_reports_the_share_kept():
    assert retained_fraction([True, True, False, False]) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="non-empty"):
        retained_fraction([])


LIDAR_CONFIG = {
    "admission_screen": SCREEN,
    "epochs": [
        epoch(name="2022"),
        epoch(
            name="2013",
            start="2013-09-28",
            end="2013-11-26",
            nominal_density_pts_m2=13.73,
            geoid="GEOID12A",
        ),
        epoch(
            name="2007",
            start="2007-03-21",
            end="2007-04-17",
            nominal_density_pts_m2=None,
            geoid=None,
            admitted=False,
        ),
    ],
}


def test_screen_epochs_admits_the_two_autumn_epochs():
    from canopyguard.lidar.harmonize import admitted_names, screen_epochs

    results = screen_epochs(LIDAR_CONFIG)
    assert admitted_names(results) == ["2022", "2013"]


def test_config_exclusion_overrides_a_passing_screen():
    from canopyguard.lidar.harmonize import screen_epochs

    config = {
        "admission_screen": SCREEN,
        "epochs": [epoch(name="2022", admitted=False)],
    }
    result = screen_epochs(config)[0]
    assert not result["admitted"]
    assert "excluded in config" in result["failures"]


def test_sample_radius_uses_the_sparsest_admitted_epoch():
    from canopyguard.lidar.harmonize import sample_radius_for, screen_epochs

    results = screen_epochs(LIDAR_CONFIG)
    radius = sample_radius_for(LIDAR_CONFIG, results)
    assert radius == pytest.approx(1.0 / np.sqrt(13.73))
