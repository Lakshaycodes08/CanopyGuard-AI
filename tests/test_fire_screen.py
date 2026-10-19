from datetime import UTC, date, datetime

import numpy as np

from canopyguard.features.fire import burned_raster, perimeters_in_window


def millis(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def feature(alarm, ring=None):
    ring = ring or [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]
    return {
        "properties": {"ALARM_DATE": alarm},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def test_window_keeps_only_fires_between_the_two_surveys():
    geojson = {
        "features": [
            feature(millis(date(2013, 6, 1))),
            feature(millis(date(2017, 10, 8))),
            feature(millis(date(2022, 10, 1))),
            feature(None),
        ]
    }
    kept = perimeters_in_window(geojson, date(2013, 11, 26), date(2022, 9, 13))
    assert len(kept) == 2


def test_burned_raster_marks_pixels_inside_a_perimeter():
    from pyproj import Transformer

    to_geo = Transformer.from_crs("EPSG:32610", "EPSG:4326", always_xy=True)
    lon0, lat0 = to_geo.transform(500000.0, 4200000.0)
    lon1, lat1 = to_geo.transform(500060.0, 4199940.0)
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    grid = (500000.0, 4200000.0, 30.0, 4, 4)
    raster = burned_raster([feature(None, ring)], grid, "EPSG:32610")
    assert raster.shape == (4, 4)
    assert raster[:2, :2].min() == 1.0
    assert raster[2:, :].max() == 0.0
    assert raster.dtype == np.float32
