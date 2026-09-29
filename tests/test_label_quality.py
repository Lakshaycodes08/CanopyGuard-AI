from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from canopyguard.lidar.label_quality import (
    build_unique_archive,
    select_unique_valid_labels,
)


def _table() -> dict[str, np.ndarray]:
    return {
        "cell_id": np.array([2, 1, 1, 1, 3]),
        "tile": np.array([5, 9, 3, 7, 4]),
        "x": np.array([25, 15, 15, 15, 35]),
        "y": np.array([5, 5, 5, 5, 5]),
        "valid_start": np.array([1.0, 0.7, 0.9, 0.9, 1.0]),
        "valid_end": np.array([1.0, 0.9, 0.8, 0.8, 1.0]),
        "mean_change": np.array([1.0, 2.0, 3.0, 4.0, np.nan]),
        "p95_change": np.array([1.0, 2.0, 3.0, 4.0, np.nan]),
        "max_change": np.array([1.0, 2.0, 3.0, 4.0, np.nan]),
    }


def test_selects_coverage_then_tile_without_using_outcome():
    unique, audit = select_unique_valid_labels(_table(), 0.5)
    assert unique["cell_id"].tolist() == [1, 2]
    assert unique["tile"].tolist() == [3, 5]
    assert unique["overlap_disputed"].tolist() == [True, False]
    assert audit["valid_rows"] == 4
    assert audit["removed_valid_overlap_rows"] == 2
    assert audit["disagreeing_cell_ids"] == 1
    assert audit["max_change_disagreement_m"]["mean_change"] == 2.0


def test_selection_is_stable_when_rows_are_reordered():
    table = _table()
    reversed_table = {key: value[::-1] for key, value in table.items()}
    selected, _ = select_unique_valid_labels(table, 0.5)
    reversed_selected, _ = select_unique_valid_labels(reversed_table, 0.5)
    assert np.array_equal(selected["tile"], reversed_selected["tile"])


def test_repeated_id_with_different_coordinates_is_rejected():
    table = _table()
    table["x"][2] = 99
    with pytest.raises(ValueError, match="different coordinates"):
        select_unique_valid_labels(table, 0.5)


def test_archive_build_checks_source_and_writes_unique_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    source = tmp_path / "source.npz"
    np.savez_compressed(source, **_table())
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    config = {
        "aggregation": {"min_valid_fraction": 0.5},
        "label_archive": {
            "source": "source.npz",
            "source_sha256": checksum,
            "unique": "out/unique.npz",
            "audit": "out/audit.json",
        },
    }
    audit = build_unique_archive(config)
    with np.load(tmp_path / "out/unique.npz", allow_pickle=False) as output:
        assert output["cell_id"].tolist() == [1, 2]
        assert output["overlap_disputed"].tolist() == [True, False]
    assert json.loads((tmp_path / "out/audit.json").read_text())["valid_rows"] == 4
    assert audit["source_sha256"] == checksum
    config["label_archive"]["source_sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash differs"):
        build_unique_archive(config)
