from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.ept import to_web_mercator
from canopyguard.lidar.sources import (
    cell_steps,
    co_covered_tiles,
    coverage_mask,
    covered_tiles,
    manifest_url,
    parse_manifest,
    union_box,
)

BOX = (-123.10, 38.40, -122.50, 38.70)


def entry(west, south, east, north, points=1_000_000):
    """One manifest entry, bounded in the frame the resource is indexed in."""
    min_x, min_y = to_web_mercator(west, south)
    max_x, max_y = to_web_mercator(east, north)
    return {"bounds": [min_x, min_y, 0.0, max_x, max_y, 100.0], "points": points}


def delivery_grid(west, south, east, north, step=0.0116):
    """A work unit as a grid of delivery tiles of about 1290 m."""
    entries = []
    latitude = south
    while latitude < north - 1e-12:
        longitude = west
        while longitude < east - 1e-12:
            entries.append(
                entry(longitude, latitude, longitude + step, latitude + step)
            )
            longitude += step
        latitude += step
    return entries


def test_manifest_url_is_the_source_listing():
    assert manifest_url("CA_NorthernCA_1_B22").endswith(
        "/CA_NorthernCA_1_B22/ept-sources/manifest.json"
    )


def test_manifest_url_rejects_a_path():
    with pytest.raises(ValueError, match="bare 3DEP project name"):
        manifest_url("a/b")


def test_parse_manifest_returns_geographic_boxes():
    boxes = parse_manifest([entry(-123.0, 38.5, -122.99, 38.51)])
    assert boxes[0][0] == pytest.approx(-123.0, abs=1e-9)
    assert boxes[0][3] == pytest.approx(38.51, abs=1e-9)


def test_parse_manifest_skips_entries_without_points_or_bounds():
    payload = [
        entry(-123.0, 38.5, -122.99, 38.51),
        entry(-122.9, 38.5, -122.89, 38.51, points=0),
        {"path": "missing.laz"},
    ]
    assert len(parse_manifest(payload)) == 1


def test_parse_manifest_rejects_an_unusable_manifest():
    with pytest.raises(ValueError, match="usable bounds"):
        parse_manifest([{"path": "a.laz"}])


def test_parse_manifest_rejects_a_non_list():
    with pytest.raises(ValueError, match="list of entries"):
        parse_manifest({"bounds": []})


def test_union_box_encloses_every_file():
    boxes = parse_manifest(
        [entry(-123.0, 38.5, -122.99, 38.51), entry(-122.9, 38.6, -122.89, 38.61)]
    )
    assert union_box(boxes) == pytest.approx((-123.0, 38.5, -122.89, 38.61), abs=1e-9)


def test_cell_steps_keep_a_tile_square_on_the_ground():
    longitude_step, latitude_step = cell_steps(BOX, 250.0, 5)
    assert longitude_step > latitude_step
    assert latitude_step == pytest.approx(250.0 / 111320.0 / 5)


def test_cell_steps_reject_a_tile_without_cells():
    with pytest.raises(ValueError, match="at least one assay cell"):
        cell_steps(BOX, 250.0, 0)


def test_coverage_counts_only_cells_wholly_inside_a_file():
    """Partial cover is no cover, so an admitted tile can be supplied in full."""
    steps = (0.01, 0.01)
    box = (0.0, 0.0, 0.1, 0.1)
    mask = coverage_mask([(0.005, 0.005, 0.045, 0.045)], box, steps)
    assert mask.shape == (10, 10)
    assert mask[1:4, 1:4].all()
    assert not mask[0, 0]
    assert mask.sum() == 9


def test_coverage_rejects_a_degenerate_box():
    with pytest.raises(ValueError, match="west < east"):
        coverage_mask([], (1.0, 0.0, 0.0, 1.0), (0.1, 0.1))


def test_covered_tiles_need_every_footprint():
    first = np.ones((10, 10), dtype=bool)
    second = np.zeros((10, 10), dtype=bool)
    second[:5, :5] = True
    tiles = covered_tiles([first, second], (0.0, 0.0, 1.0, 1.0), (0.1, 0.1), 5)
    assert len(tiles) == 1
    assert tiles[0] == pytest.approx((0.0, 0.0, 0.5, 0.5))


def test_covered_tiles_reject_mismatched_masks():
    with pytest.raises(ValueError, match="share a grid"):
        covered_tiles(
            [np.ones((4, 4), dtype=bool), np.ones((5, 5), dtype=bool)],
            (0.0, 0.0, 1.0, 1.0),
            (0.25, 0.25),
            2,
        )


def test_a_seam_narrower_than_the_tile_yields_nothing():
    """Two work units that abut share a seam of half-overlapping delivery
    tiles, about 870 m wide here. A tile wider than the seam is supplied by
    one acquisition only, which is why the original 1000 m tile read empty."""
    left = parse_manifest([entry(-123.000, 38.50, -122.800, 38.60)])
    right = parse_manifest([entry(-122.810, 38.50, -122.600, 38.60)])
    assert co_covered_tiles([left, right], BOX, 1000.0) == []
    assert co_covered_tiles([left, right], BOX, 250.0)


def test_co_covered_tiles_stay_inside_both_work_units():
    left = parse_manifest(delivery_grid(-123.00, 38.50, -122.80, 38.65))
    right = parse_manifest(delivery_grid(-122.85, 38.50, -122.60, 38.65))
    tiles = co_covered_tiles([left, right], BOX, 250.0)
    assert tiles
    east_of_left = union_box(left)[2]
    for west, _, east, _ in tiles:
        assert west >= -122.8501
        assert east <= east_of_left + 1e-9


def test_disjoint_work_units_share_no_tile():
    left = parse_manifest([entry(-123.0, 38.50, -122.90, 38.60)])
    right = parse_manifest([entry(-122.80, 38.50, -122.70, 38.60)])
    assert co_covered_tiles([left, right], BOX, 250.0) == []
