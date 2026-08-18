from pathlib import Path

import pytest

from canopyguard.config import load_config, require_keys


def test_load_config_returns_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("seed: 42\n", encoding="utf-8")

    assert load_config(path) == {"seed": 42}


def test_require_keys_reports_missing_key() -> None:
    with pytest.raises(ValueError, match="Missing"):
        require_keys({"seed": 42}, ["seed", "study_area"])
