import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_echosat_percent.py"


def load_script():
    spec = importlib.util.spec_from_file_location("import_echosat_percent", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_echosat_percent"] = module
    spec.loader.exec_module(module)
    return module


def test_expected_grid_matches_the_landsat_grid_in_blocks():
    module = load_script()
    region = {"bbox": (-122.90, 38.475, -122.74, 38.82)}
    landsat = {
        "grid_crs": "EPSG:32610",
        "grid_resolution_m": 30,
        "grid_origin_offset_m": 15,
    }
    left, top, size, shape = module.expected_grid(region, landsat, 3)
    assert (left, top, size) == (508695.0, 4296855.0, 90.0)
    assert shape == (426, 154)


def test_a_wrong_sized_export_is_rejected(tmp_path, monkeypatch):
    module = load_script()
    path = tmp_path / "bad.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="uint8",
        crs="EPSG:32610",
        transform=from_origin(508695.0, 4296855.0, 90.0, 90.0),
    ) as dst:
        dst.write(np.zeros((1, 4, 4), dtype=np.uint8))
    monkeypatch.setattr(sys, "argv", ["x", "--region", "study", "--file", str(path)])
    with pytest.raises(ValueError, match="Expected uint8"):
        module.main()
