"""Offline checks for the static 3DEP feature calculation."""

import numpy as np
import pytest
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from canopyguard.data import terrain_dem
from canopyguard.features import terrain


def test_cell_ids_and_centres_align_to_label_grid():
    transform = from_origin(0, 30, 10, 10)
    ids = np.array([2, 10_000_001])
    rows, cols = terrain._sample_indices(
        ids, np.array([5.0, 15.0]), np.array([25.0, 15.0]), transform, 10
    )
    assert rows.tolist() == [0, 1]
    assert cols.tolist() == [0, 1]
    with pytest.raises(ValueError, match="DEM grid"):
        terrain._sample_indices(
            ids, np.array([5.1, 15.0]), np.array([25.0, 15.0]), transform, 10
        )


def test_buffer_covers_450_m_tpi_window():
    box = (-122.9, 38.475, -122.74, 38.82)
    shape, transform = terrain._target_grid(box, "EPSG:6339", 10, 500)
    west, south, east, north = transform_bounds("EPSG:4326", "EPSG:6339", *box)
    assert transform.c <= west - 500
    assert transform.f >= north + 500
    assert transform.c + shape[1] * 10 >= east + 500
    assert transform.f - shape[0] * 10 <= south - 500


def test_slope_and_tpi_on_known_surfaces():
    east = np.arange(11) * 10
    plane = np.broadcast_to(-0.1 * east, (11, 11)).copy()
    slope, aspect = terrain._slope_aspect(plane, 10)
    assert slope[5, 5] == pytest.approx(np.degrees(np.arctan(0.1)))
    assert aspect[5, 5] == pytest.approx(90)
    assert terrain._tpi(plane, 10, 20)[5, 5] == pytest.approx(0, abs=1e-5)
    hill = np.zeros((11, 11), dtype=np.float32)
    hill[5, 5] = 10
    assert terrain._tpi(hill, 10, 20)[5, 5] == pytest.approx(
        10 * (1 - 1 / 13), abs=1e-5
    )


def test_nodata_does_not_enter_slope_or_tpi_as_zero():
    dem = np.ones((11, 11), dtype=np.float32)
    dem[5, 5] = np.nan
    slope, _ = terrain._slope_aspect(dem, 10)
    tpi = terrain._tpi(dem, 10, 20)
    assert np.isnan(slope[5, 5])
    assert np.isnan(slope[5, 6])
    assert np.isnan(tpi[5, 5])
    assert np.isnan(tpi[5, 6])
    assert tpi[2, 2] == pytest.approx(0, abs=1e-5)


def test_heat_load_uses_aspect_slope_and_latitude():
    slope = np.array([30.0, 30.0])
    aspect = np.array([45.0, 225.0])
    latitude = np.array([38.6, 38.6])
    cool, warm = terrain._heat_load(slope, aspect, latitude)
    assert warm > cool
    assert np.isfinite([cool, warm]).all()


def test_builder_reads_only_cell_id_and_centres(monkeypatch, tmp_path):
    class StopAfterSchemaCheck(Exception):
        pass

    def guarded_read(_path, *, columns):
        assert columns == ["cell_id", "x", "y"]
        raise StopAfterSchemaCheck

    monkeypatch.setattr(terrain, "project_root", lambda: tmp_path)
    monkeypatch.setattr(terrain, "read_provenance", lambda _path: {"sha256": "x"})
    monkeypatch.setattr(terrain.pd, "read_parquet", guarded_read)
    forecast = {
        "stage1_growth_model": {"clean_screen": {"output_path": "clean.parquet"}},
        "stage2_residual_model": {
            "terrain": {
                "target_crs": "EPSG:6339",
                "padding_m": 500,
                "tpi_radius_m": 450,
                "dem_path": "dem.tif",
            }
        },
    }
    with pytest.raises(StopAfterSchemaCheck):
        terrain.build_terrain_table(forecast, {"study_area": {}}, "EPSG:6339")


def test_dem_fetch_requires_provenance_before_reusing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(terrain_dem, "project_root", lambda: tmp_path)
    forecast = {
        "stage2_residual_model": {
            "terrain": {
                "dem_path": "dem.tif",
                "dem_url": "https://example.test/dem.tif",
            }
        }
    }
    path = tmp_path / "dem.tif"
    path.write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="lacks provenance"):
        terrain_dem.fetch_terrain_dem(forecast, {})
    (tmp_path / "dem.tif.provenance.json").write_text("{}")
    monkeypatch.setattr(terrain_dem, "read_provenance", lambda _path: {})
    assert terrain_dem.fetch_terrain_dem(forecast, {}) == path
