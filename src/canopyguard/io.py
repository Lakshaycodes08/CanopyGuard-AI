from __future__ import annotations

import base64
import re
from pathlib import Path

_DUMP_START = re.compile(r"^=== dump (\S+) base64 \d+ bytes ===$")


def project_root(start: str | Path | None = None) -> Path:
    """Return the repository root by walking up to `pyproject.toml`."""
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for path in (current, *current.parents):
        if (path / "pyproject.toml").exists():
            return path

    msg = f"Could not find project root from {current}"
    raise FileNotFoundError(msg)


def data_path(*parts: str, root: str | Path | None = None) -> Path:
    """Build a path inside the local data directory."""
    data_directory = (project_root(root) / "data").resolve()
    path = (data_directory / Path(*parts)).resolve()
    if not path.is_relative_to(data_directory):
        msg = f"Data path must stay inside {data_directory}: {path}"
        raise ValueError(msg)
    return path


def ensure_parent(path: str | Path) -> Path:
    """Create the parent directory for a file path and return the path."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def extract_dumps(log_path: str | Path, out_dir: str | Path) -> list[str]:
    """Pull base64-framed file dumps out of a colab_bootstrap.py run log.

    Reads the "=== dump <name> base64 ... ===" / "=== dump <name> end ==="
    markers written by that script's dump_outputs(), for the case where a
    stale connection blocks fetching the file directly from the VM but its
    bytes already reached the local log through the same stream that
    carried the run's other output.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    written = []
    index = 0
    while index < len(lines):
        match = _DUMP_START.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        end_marker = f"=== dump {name} end ==="
        index += 1
        start = index
        while index < len(lines) and lines[index] != end_marker:
            index += 1
        payload = "".join(lines[start:index])
        (out / name).write_bytes(base64.b64decode(payload))
        written.append(name)
        index += 1
    return written
