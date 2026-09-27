import base64
from pathlib import Path

import pytest

from canopyguard.io import data_path, ensure_parent, extract_dumps, project_root


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


def test_extract_dumps_decodes_framed_payload(tmp_path: Path) -> None:
    payload = base64.b64encode(b"hello world").decode("ascii")
    log = tmp_path / "run.log"
    log.write_text(
        "some earlier output\n"
        f"=== dump result.txt base64 {len(payload)} bytes ===\n"
        f"{payload}\n"
        "=== dump result.txt end ===\n"
        "trailing output\n"
    )
    out_dir = tmp_path / "out"

    written = extract_dumps(log, out_dir)

    assert written == ["result.txt"]
    assert (out_dir / "result.txt").read_bytes() == b"hello world"


def test_extract_dumps_splits_a_long_base64_payload_across_lines(
    tmp_path: Path,
) -> None:
    payload = base64.b64encode(b"x" * 200).decode("ascii")
    half = len(payload) // 2
    log = tmp_path / "run.log"
    log.write_text(
        f"=== dump big.bin base64 {len(payload)} bytes ===\n"
        f"{payload[:half]}\n{payload[half:]}\n"
        "=== dump big.bin end ===\n"
    )

    extract_dumps(log, tmp_path / "out")

    assert (tmp_path / "out" / "big.bin").read_bytes() == b"x" * 200


def test_extract_dumps_returns_empty_list_without_markers(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text("nothing to see here\n")

    assert extract_dumps(log, tmp_path / "out") == []
