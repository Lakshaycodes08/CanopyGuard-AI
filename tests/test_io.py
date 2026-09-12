from pathlib import Path

import pytest

from canopyguard.io import data_path, ensure_parent, project_root


def test_project_root_finds_pyproject() -> None:
    root = project_root(Path(__file__))

    assert (root / "pyproject.toml").exists()


def test_data_path_uses_project_data_dir() -> None:
    path = data_path("processed", "risk.parquet", root=Path(__file__))

    assert path.parts[-3:] == ("data", "processed", "risk.parquet")


@pytest.mark.parametrize("part", ["../outside.txt", "../../outside.txt"])
def test_data_path_rejects_parent_traversal(part: str) -> None:
    with pytest.raises(ValueError, match="must stay inside"):
        data_path(part, root=Path(__file__))


def test_data_path_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must stay inside"):
        data_path(str(tmp_path / "outside.txt"), root=Path(__file__))


def test_ensure_parent_creates_directory(tmp_path: Path) -> None:
    path = ensure_parent(tmp_path / "nested" / "file.txt")

    assert path.parent.exists()
