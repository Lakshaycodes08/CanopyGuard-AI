from pathlib import Path

import pytest

from canopyguard.config import load_config, require_keys, validate_time_splits


def test_load_config_returns_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("seed: 42\n", encoding="utf-8")

    assert load_config(path) == {"seed": 42}


@pytest.mark.parametrize("content", ["[]\n", "false\n", "0\n"])
def test_load_config_rejects_non_mapping_yaml(tmp_path: Path, content: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="YAML mapping"):
        load_config(path)


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).parents[1] / "configs").glob("*.yaml")),
    ids=lambda path: path.name,
)
def test_project_configs_are_mappings(path: Path) -> None:
    assert load_config(path)


def test_require_keys_reports_missing_key() -> None:
    with pytest.raises(ValueError, match="Missing"):
        require_keys({"seed": 42}, ["seed", "study_area"])


def test_project_time_splits_are_strictly_chronological() -> None:
    path = Path(__file__).parents[1] / "configs" / "study_area.yaml"

    validate_time_splits(load_config(path))


def test_time_splits_reject_overlap() -> None:
    config = {
        "dates": {"start": "2017-01-01", "end": "2022-12-31"},
        "splits": {
            "train_end": "2020-12-31",
            "validation_start": "2020-12-31",
            "validation_end": "2021-12-31",
            "test_start": "2022-01-01",
            "test_end": "2022-12-30",
        },
    }

    with pytest.raises(ValueError, match="non-overlapping"):
        validate_time_splits(config)
