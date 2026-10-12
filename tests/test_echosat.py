from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from canopyguard.data import echosat
from canopyguard.viz.echosat import save_sample_figure

NODATA = -9999
ORIGIN = (508000.0, 4260000.0)
SIZE = 40
YEARS = [2018, 2019, 2020]


@pytest.fixture
def source() -> dict:
    return {
        "tile_url": "https://example.test/tile.tif",
        "band_years": YEARS,
        "check_years": [2018, 2019, 2021],
        "nodata_value": NODATA,
        "height_scale_to_m": 0.01,
        "abrupt_change_m": 5,
        "request_timeout_seconds": 5,
        "http_max_retry": 1,
    }


@pytest.fixture
def raster_path(tmp_path: Path) -> Path:
    data = np.full((3, SIZE, SIZE), 1000, dtype="int16")
    data[1] += 100
    data[2, 15:20, 15:20] = 100
    data[:, :4, :] = NODATA
    path = tmp_path / "tile.tif"
    profile = {
        "driver": "GTiff",
        "count": 3,
        "width": SIZE,
        "height": SIZE,
        "dtype": "int16",
        "crs": "EPSG:32610",
        "transform": from_origin(*ORIGIN, 10, 10),
        "nodata": NODATA,
    }
    with rasterio.open(path, "w", **profile) as destination:
        destination.write(data)
    return path


def lonlat_box(x_range: tuple[float, float], y_range: tuple[float, float]):
    """Lon/lat box that encloses a UTM rectangle."""
    transformer = Transformer.from_crs("EPSG:32610", "EPSG:4326", always_xy=True)
    corners = [(x, y) for x in x_range for y in y_range]
    lon, lat = zip(*(transformer.transform(x, y) for x, y in corners), strict=True)
    return (min(lon), min(lat), max(lon), max(lat))


def test_inside_box_mask_selects_pixel_centres_in_lonlat_box() -> None:
    transform = from_origin(*ORIGIN, 10, 10)
    bbox = lonlat_box((508100, 508300), (4259700, 4259900))

    mask = echosat.inside_box_mask(transform, (SIZE, SIZE), "EPSG:32610", bbox)

    assert 400 <= mask.sum() <= 460
    assert mask[15:25, 10:30].all()
    assert not mask[0, 0]


def test_box_window_flags_partial_cover_and_no_overlap(raster_path: Path) -> None:
    with rasterio.open(raster_path) as src:
        inside = lonlat_box((508100, 508300), (4259700, 4259900))
        edge = lonlat_box((508200, 508600), (4259700, 4259900))
        far = lonlat_box((600000, 600100), (4000000, 4000100))

        assert echosat.box_window(src, inside)[1] is True
        assert echosat.box_window(src, edge)[1] is False
        with pytest.raises(ValueError, match="does not intersect"):
            echosat.box_window(src, far)


def test_count_valid_by_year_excludes_nodata() -> None:
    data = np.array([[[500, NODATA], [700, 900]], [[NODATA, NODATA], [800, 800]]])
    inside = np.array([[True, True], [True, False]])

    first, second = echosat.count_valid_by_year(
        data, inside, [2018, 2019], NODATA, 100.0, 0.01
    )

    assert (first["box_pixels"], first["valid_pixels"]) == (3, 2)
    assert first["valid_area_km2"] == pytest.approx(200 / 1e6)
    assert first["height_m"]["max"] == pytest.approx(7.0)
    assert second["valid_pixels"] == 1


def test_count_valid_by_year_reports_empty_year() -> None:
    data = np.full((1, 2, 2), NODATA)
    inside = np.ones((2, 2), dtype=bool)

    (record,) = echosat.count_valid_by_year(data, inside, [2018], NODATA, 100.0, 0.01)

    assert record["valid_pixels"] == 0
    assert "height_m" not in record


def test_count_abrupt_changes_splits_drops_and_gains() -> None:
    data = np.array([[[1000, 1000, 1000]], [[100, 1700, 1050]], [[100, 1700, NODATA]]])
    inside = np.ones((1, 3), dtype=bool)

    first, second = echosat.count_abrupt_changes(
        data, inside, [2018, 2019, 2020], NODATA, 5, 0.01
    )

    assert (first["drop_pixels"], first["gain_pixels"]) == (1, 1)
    assert (second["drop_pixels"], second["gain_pixels"]) == (0, 0)


def test_validate_raster_rejects_layout_mismatch(
    raster_path: Path, source: dict
) -> None:
    with rasterio.open(raster_path) as src:
        echosat.validate_raster(src, source)
        with pytest.raises(ValueError, match="bands"):
            echosat.validate_raster(src, {**source, "band_years": [2018, 2019]})
        with pytest.raises(ValueError, match="nodata"):
            echosat.validate_raster(src, {**source, "nodata_value": 0})


def test_build_report_counts_years_and_flags_missing_year(
    raster_path: Path, source: dict
) -> None:
    bbox = lonlat_box((508100, 508300), (4259700, 4259900))
    with rasterio.open(raster_path) as src:
        box = echosat.read_box(src, bbox)
        report = echosat.build_report(src, box, source)

    assert report["years_missing_from_product"] == [2021]
    assert [row["year"] for row in report["per_year"]] == [2018, 2019]
    assert report["raster_footprint_covers_box"] is True
    assert report["per_year"][0]["valid_share"] == pytest.approx(1.0)
    assert report["abrupt_changes"][1]["drop_pixels"] == 25


def test_write_box_copy_round_trips_bands(raster_path: Path, tmp_path: Path) -> None:
    bbox = lonlat_box((508100, 508300), (4259700, 4259900))
    with rasterio.open(raster_path) as src:
        box = echosat.read_box(src, bbox)
        copy = echosat.write_box_copy(src, box, tmp_path / "out" / "copy.tif")

    with rasterio.open(copy) as saved:
        assert saved.count == 3
        assert saved.nodata == NODATA
        assert np.array_equal(saved.read(), box.data)


def test_save_sample_figure_writes_png(tmp_path: Path) -> None:
    data = np.full((3, 8, 8), 1500, dtype="int16")
    inside = np.ones((8, 8), dtype=bool)
    figure = {"downsample": 2, "dpi": 50, "height_vmax_m": 30, "change_limit_m": 10}

    output = save_sample_figure(
        data, inside, YEARS, [2018, 2020], NODATA, figure, 0.01, tmp_path / "f.png"
    )

    assert output.stat().st_size > 0
