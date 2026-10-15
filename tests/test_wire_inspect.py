import csv

import numpy as np

from canopyguard.lidar.wire_inspect import (
    FIELDS,
    _load_done,
    summarise,
    summarise_inspection,
)

CFG = {
    "cell_m": 10.0,
    "beneath_radius_m": 2.0,
    "beneath_min_height_m": 2.0,
    "beneath_gap_m": 1.0,
}


def points(x, y, z, cls):
    n = len(x)
    return {
        "x": np.array(x, float),
        "y": np.array(y, float),
        "z": np.array(z, float),
        "cls": np.array(cls, int),
        "rn": np.ones(n, int),
        "nr": np.ones(n, int),
    }


def ground(seed):
    rng = np.random.default_rng(seed)
    return rng.uniform(-20, 20, 200), rng.uniform(-20, 20, 200)


def test_wire_like_cell_has_nothing_beneath_the_apex():
    gx, gy = ground(0)
    pts = points(
        [*gx, 0.5, 1.0],
        [*gy, 0.2, 0.3],
        [100.0] * 200 + [125.0, 125.1],
        [2] * 200 + [14, 14],
    )
    out = summarise(pts, (0.0, 0.0), CFG)
    assert out["status"] == "ok"
    assert out["apex_class"] == 14
    assert out["wire_points_class14"] == 2
    assert out["points_below_apex_2m"] == 0


def test_tree_cell_has_points_beneath_the_apex():
    gx, gy = ground(1)
    rng = np.random.default_rng(2)
    tx, ty = rng.uniform(-0.8, 0.8, 40), rng.uniform(-0.8, 0.8, 40)
    tz = 100.0 + np.linspace(3, 25, 40)
    pts = points(
        list(gx) + list(tx),
        list(gy) + list(ty),
        [100.0] * 200 + list(tz),
        [2] * 200 + [5] * 40,
    )
    out = summarise(pts, (0.0, 0.0), CFG)
    assert out["apex_class"] == 5
    assert out["points_below_apex_2m"] >= 30


def test_cell_without_ground_is_reported():
    out = summarise(points([0.0], [0.0], [130.0], [1]), (0.0, 0.0), CFG)
    assert out["status"] == "no_ground_in_window"


def test_inspection_summary_uses_only_the_flagged_epoch(tmp_path):
    path = tmp_path / "summary.csv"
    header = [
        "group",
        "flag_epoch",
        "cell_id",
        "epoch",
        "status",
        "points_below_apex_2m",
        "apex_class",
        "apex_height_m",
        "wire_points_class14",
        "tower_points_class15",
    ]
    rows = [
        ["near_line", "start", "1", "2013", "ok", "0", "1", "25", "0", "0"],
        ["near_line", "start", "1", "2022", "ok", "90", "1", "25", "0", "0"],
        ["near_line", "end", "2", "2022", "ok", "50", "1", "30", "0", "0"],
        [
            "near_line",
            "end",
            "2",
            "2013",
            "read_error:RuntimeError",
            "",
            "",
            "",
            "",
            "",
        ],
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    out = summarise_inspection(str(path), 10)
    assert out["2013_near_line"]["cells"] == 1
    assert out["2013_near_line"]["thin"] == 1
    assert out["2022_near_line"]["cells"] == 1
    assert out["2022_near_line"]["thin"] == 0


def test_failed_reads_are_dropped_so_they_can_be_retried(tmp_path):
    path = tmp_path / "summary.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(
            {"cell_id": "1", "epoch": "2013", "flag_epoch": "start", "status": "ok"}
        )
        writer.writerow(
            {
                "cell_id": "2",
                "epoch": "2013",
                "flag_epoch": "start",
                "status": "read_error:RuntimeError",
            }
        )
    done = _load_done(path, retry_failed=True)
    assert done == {("1", "2013", "start")}
    with open(path, newline="") as handle:
        assert [r["cell_id"] for r in csv.DictReader(handle)] == ["1"]
    assert _load_done(path, retry_failed=False) == {("1", "2013", "start")}


def test_inspection_summary_lists_failed_reads(tmp_path):
    path = tmp_path / "summary.csv"
    header = [
        "group",
        "flag_epoch",
        "cell_id",
        "epoch",
        "status",
        "points_below_apex_2m",
        "apex_class",
        "apex_height_m",
        "wire_points_class14",
        "tower_points_class15",
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(
            [
                "near_line",
                "start",
                "7",
                "2013",
                "read_error:RuntimeError",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    out = summarise_inspection(str(path), 10)
    assert out["failed_reads"][0]["cell_id"] == "7"
    assert out["cell_epochs_not_read"] == 1
