from __future__ import annotations

import json

import pytest

from canopyguard.config import load_config
from canopyguard.provenance import (
    boxes_intersect,
    file_sha256,
    read_provenance,
    sidecar_path,
    study_area_box,
    tracked_data_files,
    write_provenance,
)

SONOMA = (-122.90, 38.475, -122.74, 38.82)
POTOMAC = (-77.165, 38.720, -76.915, 39.018)


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text('{"value": 1}\n', encoding="utf-8")
    return path


def test_file_sha256_is_stable(data_file):
    assert file_sha256(data_file) == file_sha256(data_file)
    assert len(file_sha256(data_file)) == 64


def test_write_then_read_roundtrip(data_file):
    write_provenance(
        data_file,
        source_url="https://example.org/item",
        script_name="tests",
        bbox_wgs84=SONOMA,
        crs="EPSG:4326",
        row_count=1,
    )
    record = read_provenance(data_file)
    assert record["sha256"] == file_sha256(data_file)
    assert tuple(record["bbox_wgs84"]) == SONOMA


def test_read_rejects_missing_sidecar(data_file):
    with pytest.raises(FileNotFoundError):
        read_provenance(data_file)


def test_read_rejects_incomplete_sidecar(data_file):
    sidecar_path(data_file).write_text(json.dumps({"source_url": "x"}), "utf-8")
    with pytest.raises(ValueError, match="Missing required config keys"):
        read_provenance(data_file)


def test_read_rejects_a_data_file_modified_after_its_sidecar(data_file):
    write_provenance(
        data_file,
        source_url="https://example.org/item",
        script_name="tests",
        bbox_wgs84=SONOMA,
        crs="EPSG:4326",
        row_count=1,
    )
    data_file.write_text('{"value": 2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its provenance sidecar"):
        read_provenance(data_file)


def test_boxes_intersect_detects_wrong_region():
    assert boxes_intersect(SONOMA, SONOMA)
    assert not boxes_intersect(SONOMA, POTOMAC)


def test_study_area_box_matches_config():
    study_config = load_config("configs/study_area.yaml")
    assert boxes_intersect(study_area_box(study_config), SONOMA)


def test_every_data_file_declares_provenance_inside_the_study_area():
    study_box = study_area_box(load_config("configs/study_area.yaml"))
    for path in tracked_data_files():
        record = read_provenance(path)
        declared = tuple(record["bbox_wgs84"])
        assert boxes_intersect(declared, study_box), path
