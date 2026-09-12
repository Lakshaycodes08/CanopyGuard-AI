from pathlib import Path

import pytest

from canopyguard.config import load_config, require_keys


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
