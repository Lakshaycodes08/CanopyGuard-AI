from __future__ import annotations

import math

import pytest

from canopyguard.lidar.ept import (
    box_to_web_mercator,
    ept_url,
    mercator_scale,
    parse_ept,
    pdal_bounds,
    pulse_density,
    reader_stage,
    return_density,
    to_web_mercator,
)

CALIBRATION = (-123.39, 38.79, -122.36, 38.93)


def test_ept_url_uses_the_project_short_name():
    url = ept_url("CA_NorthCoastRanges_2_B23")
    assert url.endswith("/CA_NorthCoastRanges_2_B23/ept.json")


def test_ept_url_rejects_a_path():
    with pytest.raises(ValueError, match="bare 3DEP project name"):
        ept_url("a/b")


def test_web_mercator_origin_and_sign():
    x, y = to_web_mercator(0.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)
    x, y = to_web_mercator(-122.8, 38.86)
    assert x < 0
    assert y > 0


def test_web_mercator_matches_the_published_resource_bounds():
    """The 2023 resource conforming bounds sit near these mercator values."""
    x, _ = to_web_mercator(-123.39, 38.79)
    assert x == pytest.approx(-13735000, abs=5000)


def test_box_to_web_mercator_preserves_ordering():
    min_x, min_y, max_x, max_y = box_to_web_mercator(CALIBRATION)
    assert min_x < max_x
    assert min_y < max_y


def test_box_to_web_mercator_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="west < east"):
        box_to_web_mercator((1.0, 0.0, 0.0, 1.0))


def test_pdal_bounds_is_the_paired_range_form():
    assert pdal_bounds((1.0, 2.0, 3.0, 4.0)) == "([1.0,3.0],[2.0,4.0])"


def test_mercator_scale_inflates_away_from_the_equator():
    assert mercator_scale(0.0) == pytest.approx(1.0)
    assert mercator_scale(38.86) == pytest.approx(1.0 / math.cos(math.radians(38.86)))


def test_parse_ept_extracts_the_pipeline_fields():
    payload = {
        "bounds": [-13749621, 4601198, -90937, -13565687, 4785132, 92997],
        "boundsConforming": [-13735021, 4601198, -142, -13580286, 4785131, 2202],
        "points": 186415389199,
        "span": 128,
        "dataType": "laszip",
        "srs": {"authority": "EPSG", "horizontal": "3857"},
    }
    parsed = parse_ept(payload)
    assert parsed["points"] == 186415389199
    assert parsed["horizontal_epsg"] == "3857"
    assert parsed["span"] == 128
    assert len(parsed["bounds_conforming"]) == 6


def test_parse_ept_names_a_missing_field():
    with pytest.raises(ValueError, match="missing points"):
        parse_ept({"bounds": [], "srs": {}})


def test_return_density_reproduces_the_published_figures():
    """Returns per square metre, not pulses. Both epochs use the same measure."""
    assert return_density(186415389199, 8742.25) == pytest.approx(21.3, abs=0.1)
    assert return_density(95945998233, 4460.27) == pytest.approx(21.5, abs=0.1)


def test_pulse_density_is_the_nominal_spacing_measure():
    """A 0.35 m nominal pulse spacing is 8.16 pulses per square metre."""
    assert pulse_density(0.35) == pytest.approx(8.16, abs=0.01)


def test_density_measures_must_not_be_mixed():
    returns = return_density(186415389199, 8742.25)
    pulses = pulse_density(0.35)
    assert returns > 2 * pulses


def test_reader_stage_requests_only_the_window():
    stage = reader_stage("CA_NorthernCA_1_B22", CALIBRATION)
    assert stage["type"] == "readers.ept"
    assert stage["filename"].endswith("CA_NorthernCA_1_B22/ept.json")
    assert stage["bounds"].startswith("([")
    assert stage["threads"] == 4
