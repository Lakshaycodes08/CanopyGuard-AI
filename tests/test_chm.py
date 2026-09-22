from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.chm import (
    build_layer_pipeline,
    build_terrain_pipeline,
    class_filter_stage,
    decimation_stage,
    ground_stage,
    hag_stage,
    height_threshold_stage,
    pit_free_combine,
    raster_stage,
    scan_angle_stage,
)

CONFIG = {
    "harmonization": {
        "target_crs": "EPSG:6339",
        "drop_classes": [7, 9, 12, 18],
        "max_scan_angle_deg": 15.0,
        "sample_radius_m": 0.27,
    },
    "chm": {
        "resolution_m": 1.0,
        "dtm_output_type": "idw",
        "dsm_output_type": "max",
        "height_above_ground": "hag_delaunay",
        "smrf": {"scalar": 1.25, "slope": 0.15, "threshold": 0.5, "window": 18.0},
    },
}


def test_class_filter_excludes_the_listed_classes():
    stage = class_filter_stage([7, 9])
    assert stage["type"] == "filters.range"
    assert "Classification!" in stage["limits"]


def test_class_filter_requires_a_class():
    with pytest.raises(ValueError, match="At least one class"):
        class_filter_stage([])


def test_scan_angle_stage_is_symmetric():
    assert scan_angle_stage(15.0)["limits"] == "ScanAngleRank[-15.0:15.0]"


def test_decimation_stage_carries_the_radius():
    assert decimation_stage(0.27)["radius"] == pytest.approx(0.27)
    with pytest.raises(ValueError, match="must be positive"):
        decimation_stage(0.0)


def test_ground_stage_names_missing_parameters():
    with pytest.raises(ValueError, match="Missing SMRF parameters"):
        ground_stage({"scalar": 1.25})


def test_hag_stage_rejects_an_unknown_method():
    assert hag_stage("hag_nn")["type"] == "filters.hag_nn"
    with pytest.raises(ValueError, match="must be one of"):
        hag_stage("hag_guess")


def test_raster_stage_optionally_names_a_dimension():
    plain = raster_stage("a.tif", "max", 1.0)
    dimensioned = raster_stage("b.tif", "max", 1.0, "HeightAboveGround")
    assert "dimension" not in plain
    assert dimensioned["dimension"] == "HeightAboveGround"


def test_height_threshold_stage_is_open_ended():
    assert height_threshold_stage(5.0)["limits"] == "HeightAboveGround[5.0:]"


def test_terrain_pipeline_writes_both_surfaces_after_ground_classification():
    built = build_terrain_pipeline("in.laz", "dtm.tif", "dsm.tif", CONFIG)
    pipeline = built["pipeline"]
    types = [stage["type"] for stage in pipeline]
    assert types[0] == "readers.las"
    assert types.index("filters.smrf") < types.index("writers.gdal")
    assert sum(1 for stage in pipeline if stage["type"] == "writers.gdal") == 2


def test_layer_pipeline_thresholds_before_rasterising():
    pipeline = build_layer_pipeline("in.laz", "l.tif", 10.0, CONFIG)["pipeline"]
    limits = [s.get("limits") for s in pipeline if s["type"] == "filters.range"]
    assert "HeightAboveGround[10.0:]" in limits
    assert pipeline[-1]["dimension"] == "HeightAboveGround"


def test_every_epoch_gets_an_identical_pipeline_shape():
    """Differing stages between epochs would appear as canopy change."""
    first = build_layer_pipeline("a.laz", "a.tif", 5.0, CONFIG)["pipeline"]
    second = build_layer_pipeline("b.laz", "b.tif", 5.0, CONFIG)["pipeline"]
    assert [s["type"] for s in first] == [s["type"] for s in second]


def test_pit_free_combine_takes_the_layer_maximum():
    layers = [np.array([[1.0, 8.0]]), np.array([[5.0, 2.0]])]
    assert pit_free_combine(layers, 0.0, 120.0).tolist() == [[5.0, 8.0]]


def test_pit_free_combine_clamps_impossible_heights():
    combined = pit_free_combine([np.array([[-3.0, 400.0, 30.0]])], 0.0, 120.0)
    assert np.isnan(combined[0, 0])
    assert np.isnan(combined[0, 1])
    assert combined[0, 2] == 30.0


def test_pit_free_combine_rejects_an_empty_stack():
    with pytest.raises(ValueError, match="At least one layer"):
        pit_free_combine([], 0.0, 120.0)
