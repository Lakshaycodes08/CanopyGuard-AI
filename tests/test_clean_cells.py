"""Offline checks for issue 8's independent clean-growth screen."""

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box

from canopyguard.data.fire_perimeters import point_hits
from canopyguard.data.hansen import loss_year_at_cells
from canopyguard.evaluation.clean_cells import (
    clean_flags,
    exclusion_counts,
    wire_suspects,
)


def test_clean_flags_remove_each_declared_risk_once():
    n = 10
    labels = {
        "cell_id": np.arange(n),
        "x": np.arange(n, dtype=float),
        "y": np.zeros(n),
        "mean_start": np.full(n, 5.0),
        "loss_share": np.zeros(n),
        "overlap_disputed": np.zeros(n, dtype=bool),
    }
    labels["overlap_disputed"][1] = True
    labels["mean_start"][2] = 1.0
    labels["loss_share"][7] = 0.05
    names = ["oak"] * n
    names[3] = "uncertain"
    vegetation = pd.DataFrame(
        {
            "cell_id": labels["cell_id"],
            "vegetation_type": names,
            "broader_group": ["hardwood forest"] * n,
            "model_group": ["oak"] * n,
        }
    )
    burned = np.zeros(n, dtype=bool)
    burned[4] = True
    hansen_loss = np.zeros(n, dtype=bool)
    hansen_loss[6] = True
    hansen_valid = np.ones(n, dtype=bool)
    hansen_valid[5] = False
    near_line = np.zeros(n, dtype=bool)
    near_line[8] = True
    wire = np.zeros(n, dtype=bool)
    wire[9] = True
    table = clean_flags(
        labels,
        vegetation,
        burned,
        hansen_loss,
        hansen_valid,
        near_line,
        wire,
        {"min_mean_start_m": 2.0, "loss_share_threshold": 0.05},
    )
    audit = exclusion_counts(table)
    assert table.loc[0, "clean"]
    assert table["clean"].sum() == 1
    assert table.loc[9, "near_line"]
    assert list(audit["sequential_removed"].values()) == [1] * 7 + [2]
    assert audit["clean_by_type"] == {"oak": 1}


def test_polygon_hits_are_spatial_and_include_edges():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.zeros(4)
    assert point_hits(x, y, [box(0, -1, 1, 1)], 2).tolist() == [
        True,
        True,
        False,
        False,
    ]


def test_hansen_loss_year_uses_real_years_and_excludes_nodata(tmp_path):
    path = tmp_path / "lossyear.tif"
    values = np.array([[14, 22, 23], [0, 255, 15]], dtype=np.uint8)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=3,
        height=2,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(-123, 39, 0.01, 0.01),
        nodata=255,
    ) as target:
        target.write(values, 1)
    lon = np.array([-122.995, -122.985, -122.975, -122.995, -122.985])
    lat = np.array([38.995, 38.995, 38.995, 38.985, 38.985])
    x, y = Transformer.from_crs(4326, 6339, always_xy=True).transform(lon, lat)
    loss, valid = loss_year_at_cells(path, x, y, 2014, 2022)
    assert loss.tolist() == [True, True, False, False, False]
    assert valid.tolist() == [True, True, True, True, False]


def test_empty_wire_archive_is_available_and_safe(tmp_path):
    path = tmp_path / "wire.npz"
    np.savez(
        path,
        cell_id=np.array([], dtype=np.int64),
        wire_suspect=np.array([], dtype=bool),
    )
    flags, available = wire_suspects(path, np.array([1, 2], dtype=np.int64))
    assert available
    assert flags.tolist() == [False, False]
