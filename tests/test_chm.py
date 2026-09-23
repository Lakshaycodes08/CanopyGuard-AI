from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.chm import (
    build_layer_pipeline,
    build_terrain_pipeline,
    class_filter_stage,
    crop_stage,
    decimation_stage,
    flag_filter_stage,
    ground_only_stage,
    ground_stage,
    hag_stage,
    height_threshold_stage,
    pit_free_combine,
    raster_stage,
    reader_stage,
    return_guard_stage,
    scan_angle_stage,
    stats_stage,
)
from canopyguard.lidar.chm import pipeline_stats

CONFIG = {
    "harmonization": {
        "target_crs": "EPSG:6339",
        "drop_classes": [7, 9, 12, 18],
        "max_scan_angle_deg": 15.0,
        "sample_radius_m": 0.27,
        "drop_class_flags": True,
        "stats_dimensions": ["Z", "ScanAngleRank"],
    },
    "chm": {
        "resolution_m": 1.0,
        "dtm_output_type": "idw",
        "dsm_output_type": "max",
        "dsm_binmode": True,
        "dtm_binmode": False,
        "height_above_ground": "hag_delaunay",
        "smrf": {"scalar": 1.25, "slope": 0.15, "threshold": 0.5, "window": 18.0},
    },
}
GRID = {
    "origin_x": 500000.0,
    "origin_y": 4200000.0,
    "width": 250,
    "height": 250,
    "resolution_m": 1.0,
}


def types_of(pipeline):
    return [stage["type"] for stage in pipeline]


def test_return_guard_drops_unset_return_numbering():
    """A tile carrying a mix of valid and zero numbering aborts the ground
    classifier, so those returns are removed before it runs."""
    stage = return_guard_stage()
    assert stage["type"] == "filters.expression"
    assert stage["expression"] == "ReturnNumber > 0 && NumberOfReturns > 0"


def test_class_filter_excludes_every_listed_class():
    stage = class_filter_stage([18, 7, 12, 9])
    assert stage["type"] == "filters.expression"
    assert stage["expression"] == (
        "Classification != 7 && Classification != 9 "
        "&& Classification != 12 && Classification != 18"
    )


def test_class_filter_requires_a_class():
    with pytest.raises(ValueError, match="At least one class"):
        class_filter_stage([])


def test_scan_angle_stage_is_symmetric():
    assert scan_angle_stage(15.0)["expression"] == (
        "ScanAngleRank >= -15.0 && ScanAngleRank <= 15.0"
    )
    with pytest.raises(ValueError, match="must be positive"):
        scan_angle_stage(0.0)


def test_crop_stage_uses_a_bounds_string():
    stage = crop_stage((1.0, 2.0, 3.0, 4.0))
    assert stage["type"] == "filters.crop"
    assert stage["bounds"] == "([1.0,3.0],[2.0,4.0])"


def test_decimation_stage_carries_the_radius():
    assert decimation_stage(0.27)["radius"] == pytest.approx(0.27)
    with pytest.raises(ValueError, match="must be positive"):
        decimation_stage(0.0)


def test_ground_stage_names_missing_parameters():
    with pytest.raises(ValueError, match="Missing SMRF parameters"):
        ground_stage({"scalar": 1.25})


def test_ground_only_stage_keeps_the_ground_class():
    assert ground_only_stage()["expression"] == "Classification == 2"


def test_hag_stage_rejects_an_unknown_method():
    assert hag_stage("hag_nn")["type"] == "filters.hag_nn"
    with pytest.raises(ValueError, match="must be one of"):
        hag_stage("hag_guess")


def test_height_threshold_stage_is_open_ended():
    assert height_threshold_stage(5.0)["expression"] == "HeightAboveGround >= 5.0"


def test_raster_stage_fixes_the_grid_rather_than_inferring_it():
    """An inferred grid gives each epoch a different origin and size, and two
    such rasters cannot be differenced."""
    stage = raster_stage("a.tif", "max", GRID)
    assert stage["origin_x"] == 500000.0
    assert stage["origin_y"] == 4200000.0
    assert stage["width"] == 250
    assert stage["height"] == 250
    assert stage["resolution"] == 1.0
    assert stage["allow_empty"] is True


def test_raster_stage_optionally_names_a_dimension_and_bins():
    plain = raster_stage("a.tif", "max", GRID)
    binned = raster_stage("b.tif", "max", GRID, "HeightAboveGround", binmode=True)
    assert "dimension" not in plain
    assert plain["binmode"] is False
    assert binned["dimension"] == "HeightAboveGround"
    assert binned["binmode"] is True


def test_raster_stage_rejects_an_incomplete_grid():
    with pytest.raises(ValueError, match="missing width"):
        raster_stage("a.tif", "max", {k: v for k, v in GRID.items() if k != "width"})


def test_raster_stage_rejects_an_empty_grid():
    with pytest.raises(ValueError, match="at least one cell"):
        raster_stage("a.tif", "max", {**GRID, "width": 0})


def test_terrain_pipeline_order():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    order = types_of(pipeline)
    assert order[0] == "readers.las"
    assert order[1] == "filters.expression"
    assert pipeline[1]["expression"].startswith("ReturnNumber")
    assert order.index("filters.crop") < order.index("filters.sample")
    assert order.index("filters.sample") < order.index("filters.smrf")
    assert order.index("filters.smrf") < order.index("writers.gdal")
    assert sum(1 for stage in pipeline if stage["type"] == "writers.gdal") == 2


def test_terrain_pipeline_thins_before_classifying_ground():
    """Both epochs are classified at one density. Classifying at native
    density leaves a density-dependent ground difference, which is the one
    error that does not cancel when two epochs are subtracted."""
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    order = types_of(pipeline)
    assert order.index("filters.sample") < order.index("filters.smrf")


def test_terrain_pipeline_writes_the_surface_before_keeping_ground_only():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    writers = [i for i, stage in enumerate(pipeline) if stage["type"] == "writers.gdal"]
    ground_only = [
        i
        for i, stage in enumerate(pipeline)
        if stage.get("expression") == "Classification == 2"
    ]
    assert writers[0] < ground_only[0] < writers[1]
    assert pipeline[writers[0]]["filename"] == "dsm.tif"
    assert pipeline[writers[1]]["filename"] == "dtm.tif"


def test_both_writers_share_one_grid():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    geometries = {
        (stage["origin_x"], stage["origin_y"], stage["width"], stage["height"])
        for stage in pipeline
        if stage["type"] == "writers.gdal"
    }
    assert len(geometries) == 1


def test_crop_matches_the_raster_extent():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    crop = next(stage for stage in pipeline if stage["type"] == "filters.crop")
    assert crop["bounds"] == "([500000.0,500250.0],[4200000.0,4200250.0])"


def test_no_stage_uses_the_deprecated_range_filter():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    assert "filters.range" not in types_of(pipeline)


def test_layer_pipeline_thresholds_before_rasterising():
    pipeline = build_layer_pipeline(
        reader_stage("in.laz"), "l.tif", 10.0, GRID, CONFIG
    )["pipeline"]
    expressions = [stage.get("expression") for stage in pipeline]
    assert "HeightAboveGround >= 10.0" in expressions
    assert pipeline[-1]["dimension"] == "HeightAboveGround"


def test_every_epoch_gets_an_identical_pipeline_shape():
    """Differing stages between epochs would appear as canopy change."""
    first = build_layer_pipeline(reader_stage("a.laz"), "a.tif", 5.0, GRID, CONFIG)
    second = build_layer_pipeline(reader_stage("b.laz"), "b.tif", 5.0, GRID, CONFIG)
    assert types_of(first["pipeline"]) == types_of(second["pipeline"])


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


def test_flag_filter_drops_withheld_and_overlap():
    """Withheld and overlap are flags, not classification values, so a filter
    on Classification misses them."""
    stage = flag_filter_stage()
    assert stage["type"] == "filters.expression"
    assert stage["expression"] == "Synthetic == 0 && Withheld == 0 && Overlap == 0"


def test_flag_filter_runs_before_reprojection():
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    expressions = [stage.get("expression") for stage in pipeline]
    flags = expressions.index("Synthetic == 0 && Withheld == 0 && Overlap == 0")
    assert flags < types_of(pipeline).index("filters.reprojection")


def test_flag_filter_is_optional():
    config = {**CONFIG, "harmonization": {**CONFIG["harmonization"]}}
    config["harmonization"]["drop_class_flags"] = False
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, config
    )["pipeline"]
    assert "Synthetic == 0 && Withheld == 0 && Overlap == 0" not in [
        stage.get("expression") for stage in pipeline
    ]


def test_stats_stage_names_its_dimensions():
    assert stats_stage(["Z", "GpsTime"])["dimensions"] == "Z,GpsTime"
    with pytest.raises(ValueError, match="At least one dimension"):
        stats_stage([])


def test_statistics_are_recorded_on_the_retained_points():
    """The pipeline ends on the ground surface, so its own count is ground
    returns and the retained count has to come from earlier."""
    pipeline = build_terrain_pipeline(
        reader_stage("in.laz"), "dtm.tif", "dsm.tif", GRID, CONFIG
    )["pipeline"]
    order = types_of(pipeline)
    assert order.index("filters.stats") < order.index("filters.smrf")
    assert order.index("filters.sample") < order.index("filters.stats")


def test_pipeline_stats_reads_the_statistics_node():
    metadata = {
        "metadata": {
            "filters.stats": {
                "statistic": [
                    {"name": "Z", "count": 100, "minimum": 1.0, "maximum": 9.0,
                     "average": 5.0},
                    {"name": "ScanAngleRank", "count": 100, "minimum": -14.0,
                     "maximum": 13.0, "average": 0.2},
                ]
            }
        }
    }
    stats = pipeline_stats(metadata)
    assert stats["Z"]["count"] == 100.0
    assert stats["ScanAngleRank"]["minimum"] == -14.0


def test_pipeline_stats_tolerates_a_missing_node():
    assert pipeline_stats({"metadata": {}}) == {}
