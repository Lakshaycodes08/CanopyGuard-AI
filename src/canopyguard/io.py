from __future__ import annotations

from pathlib import Path


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
