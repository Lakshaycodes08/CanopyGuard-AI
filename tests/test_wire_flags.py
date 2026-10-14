import json

import numpy as np
from pyproj import Transformer

from canopyguard.lidar.wire_flags import (
    apply_max_p95_exclusion,
    build_flags,
    remaining_counts,
)

CFG = {
    "cell_m": 10.0,
    "min_valid_fraction": 0.5,
    "epochs": ["start", "end"],
    "spike": {
        "min_max_height_m": 10.0,
        "max_neighbour_median_m": 3.0,
        "min_neighbours": 4,
        "wire_like_gap_m": 5.0,
    },
    "bands_m": {"near": [0.0, 30.0]},
    "exclusion": {"within_line_m": 9.0, "modelling_min_mean_start_m": 2.0},
}
SIDE = 7
X0, Y0 = 500005.0, 4200005.0


def small_table():
    cols, rows = np.meshgrid(np.arange(SIDE), np.arange(SIDE), indexing="ij")
    n = SIDE * SIDE
    top = np.full(n, 1.0)
    top[24] = 25.0
    return {
        "cell_id": np.arange(n),
        "x": X0 + 10.0 * cols.ravel(),
        "y": Y0 + 10.0 * rows.ravel(),
        "valid_start": np.full(n, 0.9),
        "valid_end": np.full(n, 0.9),
        "mean_change": np.zeros(n),
        "mean_start": np.full(n, 5.0),
        "canopy_share": np.full(n, 0.5),
        "tile": np.zeros(n, dtype=int),
        "max_start": top,
        "max_end": top.copy(),
        "p95_start": np.full(n, 1.0),
        "p95_end": np.full(n, 1.0),
    }


def line_file(tmp_path):
    to_lonlat = Transformer.from_crs(6339, 4326, always_xy=True)
    x = X0 + 30.0
    ends = [to_lonlat.transform(x, Y0 - 5.0), to_lonlat.transform(x, Y0 + 75.0)]
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "LineString", "coordinates": [list(e) for e in ends]},
    }
    path = tmp_path / "lines.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    return str(path)


def test_planted_spike_on_the_line_is_flagged_and_column_is_excluded(tmp_path):
    arrays, counts = build_flags(small_table(), CFG, line_file(tmp_path))
    assert counts["wire_suspect"] == 1
    assert counts["within_exclusion_distance"] == SIDE
    assert counts["excluded_from_max_p95"] == SIDE
    assert counts["remaining_for_max_p95"] == SIDE * SIDE - SIDE
    assert counts["canopy_cells_remaining_for_max_p95"] == SIDE * SIDE - SIDE
    assert arrays["wire_suspect"].sum() == 1


def test_remaining_counts_adds_up():
    table = {"mean_start": np.array([5.0, 1.0, np.nan, 5.0])}
    arrays = {
        "wire_suspect": np.array([True, False, False, False]),
        "within_exclusion_m": np.array([False, True, False, False]),
        "exclude_max_p95": np.array([True, True, False, False]),
    }
    out = remaining_counts(table, np.arange(4), arrays, CFG, 2)
    assert out["excluded_from_max_p95"] == 2
    assert out["remaining_for_max_p95"] == 2
    assert out["canopy_cells_before"] == 2
    assert out["canopy_cells_remaining_for_max_p95"] == 1


def test_exclusion_blanks_max_and_p95_but_not_mean():
    table = {
        "cell_id": np.array([1, 2, 3]),
        "max_end": np.array([9.0, 9.0, 9.0]),
        "mean_change": np.array([1.0, 1.0, 1.0]),
    }
    flags = {
        "cell_id": np.array([1, 2]),
        "exclude_max_p95": np.array([True, False]),
    }
    out = apply_max_p95_exclusion(table, flags, ["max_end"])
    assert np.isnan(out["max_end"][0])
    assert out["max_end"][1:].tolist() == [9.0, 9.0]
    assert out["mean_change"].tolist() == [1.0, 1.0, 1.0]
