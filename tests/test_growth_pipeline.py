from datetime import date

import numpy as np
import pandas as pd
import pytest

from canopyguard.data.landsat_stac import (
    assert_before_cutoff,
    mask_and_scale,
    season_window,
    study_grid,
)
from canopyguard.features.landsat_history import trend_per_year
from canopyguard.forecasting.growth_model import (
    NON_FEATURES,
    feature_columns,
    spatial_folds,
)
from canopyguard.forecasting.growth_table import block_mean, labels_on_pixel_grid

CONFIG = {
    "cutoff": "2013-09-27",
    "season_start": "06-01",
    "season_end": "09-15",
    "grid_resolution_m": 30,
    "grid_origin_offset_m": 15,
    "qa_reject_mask": 63,
    "reflectance_scale": 0.0000275,
    "reflectance_offset": -0.2,
}


def test_scene_on_cutoff_day_is_rejected():
    with pytest.raises(ValueError, match="on or after the cutoff"):
        assert_before_cutoff([date(2013, 8, 1), date(2013, 9, 27)], date(2013, 9, 27))


def test_scene_before_cutoff_is_accepted():
    assert_before_cutoff([date(2013, 9, 26)], date(2013, 9, 27))


def test_season_never_reaches_cutoff():
    start, end = season_window(2013, {**CONFIG, "season_end": "10-30"})
    assert end < date(2013, 9, 27)
    with pytest.raises(ValueError):
        season_window(2014, CONFIG)


def test_grid_is_snapped_outward_to_landsat_pixels():
    left, top, width, height = study_grid((100.0, 200.0, 190.0, 290.0), CONFIG)
    assert (left - 15) % 30 == 0 and (top - 15) % 30 == 0
    assert left <= 100.0 and top >= 290.0
    assert left + width * 30 >= 190.0 and top - height * 30 <= 200.0


def test_cloud_and_fill_become_nan():
    raw = np.full((6, 1, 2), 10000, dtype=np.uint16)
    qa = np.array([[0, 8]], dtype=np.uint16)
    out = mask_and_scale(raw, qa, CONFIG)
    assert np.isfinite(out[:, 0, 0]).all()
    assert np.isnan(out[:, 0, 1]).all()


def test_trend_recovers_known_slope():
    years = np.arange(2001, 2014)
    series = (0.01 * (years - 2001) + 0.3).astype(np.float32)[:, None, None]
    slope = trend_per_year(np.repeat(series, 2, axis=1), years)
    assert np.allclose(slope, 0.01, atol=1e-5)


def test_labels_are_averaged_inside_each_pixel():
    grid = (0.0, 60.0, 30.0, 2, 2)
    x = np.array([5.0, 15.0, 25.0, 35.0])
    y = np.array([55.0, 45.0, 35.0, 55.0])
    labels = {
        "x": x,
        "y": y,
        "mean_change": np.array([1.0, 2.0, 3.0, 9.0]),
        "p95_change": np.array([1.0, 2.0, 3.0, 9.0]),
        "mean_start": np.zeros(4),
        "p95_start": np.zeros(4),
        "canopy_share": np.ones(4),
        "loss_share": np.zeros(4),
    }
    table = labels_on_pixel_grid(labels, grid, min_cells=3)
    assert len(table) == 1
    assert table.loc[0, "mean_change"] == pytest.approx(2.0)
    assert (table.loc[0, "row"], table.loc[0, "col"]) == (0, 0)


def test_block_mean_needs_enough_valid_pixels():
    raster = np.array([[1.0, 3.0], [np.nan, np.nan]], dtype=np.float32)
    assert block_mean(raster, 2, 0.5)[0, 0] == pytest.approx(2.0)
    assert np.isnan(block_mean(raster, 2, 0.75)[0, 0])


def test_no_lidar_column_is_a_predictor():
    columns = ["ndvi_recent", "nbr_trend", "mean_change", "p95_start", "canopy_share"]
    chosen = feature_columns(pd.DataFrame(columns=columns))
    assert chosen == ["ndvi_recent", "nbr_trend"]
    assert {"mean_change", "p95_change", "p95_start", "canopy_share"} <= NON_FEATURES


def test_spatial_folds_keep_blocks_together():
    x = np.repeat(np.arange(0.0, 40000.0, 1000.0), 5)
    table = pd.DataFrame({"x": x, "y": np.zeros(x.size)})
    folds = spatial_folds(table, 2000.0, 4, seed=1)
    for block in np.unique((x // 2000).astype(int)):
        assert np.unique(folds[(x // 2000).astype(int) == block]).size == 1
