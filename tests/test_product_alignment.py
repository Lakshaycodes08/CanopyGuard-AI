"""E8 alignment tests use small rasters and never read target LiDAR heights."""

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from canopyguard.config import load_config
from canopyguard.evaluation.product_alignment import (
    align_echosat_band,
    coordinate_operation,
    label_grid,
)

BBOX = (-122.9, 38.475, -122.74, 38.82)


def settings():
    return load_config("configs/product_benchmark.yaml")["echosat_alignment"]


def label_cells():
    x = np.array([500005.0, 500015.0, 500025.0])
    y = np.array([4280025.0, 4280015.0, 4280005.0])
    ids = (np.floor(x / 10) * 10_000_000 + np.floor(y / 10)).astype(np.int64)
    return ids, x, y


def test_pinned_operation_is_available_and_has_reported_accuracy():
    selected = coordinate_operation(settings(), BBOX)
    assert selected.operations[1].to_json_dict()["id"]["code"] == 9774
    assert selected.accuracy == 2.0
    assert selected.to_proj4() == settings()["operation_proj"]


def test_label_grid_rejects_coordinate_or_id_mismatch():
    ids, x, y = label_cells()
    transform, shape, rows, columns = label_grid(ids, x, y, 10)
    assert shape == (3, 3)
    assert transform == from_origin(500000, 4280030, 10, 10)
    assert rows.tolist() == [0, 1, 2]
    assert columns.tolist() == [0, 1, 2]
    with pytest.raises(ValueError, match="cell IDs"):
        label_grid(ids + 1, x, y, 10)
    with pytest.raises(ValueError, match="centres"):
        label_grid(ids, x + 0.2, y, 10)


def test_explicit_warp_matches_cells_and_records_offset_sensitivity():
    ids, x, y = label_cells()
    data = np.arange(9, dtype=np.int16).reshape(3, 3)
    data[0, 0] = -9999
    profile = {
        "driver": "GTiff",
        "height": 3,
        "width": 3,
        "count": 1,
        "dtype": "int16",
        "crs": "EPSG:32610",
        "transform": from_origin(500000, 4280030, 10, 10),
        "nodata": -9999,
    }
    with MemoryFile() as memory, memory.open(**profile) as source:
        source.write(data, 1)
        heights, record = align_echosat_band(
            source, 1, ids, x, y, "EPSG:6339", settings(), BBOX, 0.01
        )
        moved, moved_record = align_echosat_band(
            source,
            1,
            ids,
            x,
            y,
            "EPSG:6339",
            settings(),
            BBOX,
            0.01,
            offset_east_m=2.0,
        )
        with pytest.raises(ValueError, match="label CRS"):
            align_echosat_band(
                source, 1, ids, x, y, "EPSG:32610", settings(), BBOX, 0.01
            )
    assert np.isnan(heights[0])
    np.testing.assert_allclose(heights[1:], [0.04, 0.08], atol=1e-4)
    assert moved[1] != pytest.approx(heights[1], abs=1e-4)
    assert record["operation_epsg"] == 9774
    assert record["target_crs"] == "EPSG:6339"
    assert moved_record["offset_east_m"] == 2.0
