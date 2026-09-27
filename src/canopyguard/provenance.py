"""Provenance sidecars for files written into the data workspace."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from canopyguard.config import require_keys
from canopyguard.io import data_path, ensure_parent, project_root

SIDECAR_SUFFIX = ".provenance.json"
TRACKED_DIRECTORIES = ("interim", "processed")
IGNORED_NAMES = frozenset({".gitkeep", ".gitignore", ".DS_Store"})
REQUIRED_FIELDS = [
    "source_url",
    "fetch_utc",
    "sha256",
    "bbox_wgs84",
    "crs",
    "git_commit",
    "script_name",
]

Box = tuple[float, float, float, float]


def file_sha256(path: str | Path) -> str:
    """Return the SHA256 hex digest of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def current_commit(root: str | Path | None = None) -> str:
    """Return the current git commit, or 'unknown' outside a repository."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=project_root(root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def sidecar_path(path: str | Path) -> Path:
    """Return the sidecar path for a data file."""
    return Path(f"{path}{SIDECAR_SUFFIX}")


def study_area_box(study_config: dict[str, Any]) -> Box:
    """Extract the study-area bounding box as west, south, east, north."""
    require_keys(study_config, ["study_area"])
    bbox = study_config["study_area"]["bbox"]
    return tuple(float(bbox[key]) for key in ("west", "south", "east", "north"))


def boxes_intersect(left: Box, right: Box) -> bool:
    """Return True when two west, south, east, north boxes overlap."""
    return (
        left[0] < right[2]
        and right[0] < left[2]
        and left[1] < right[3]
        and right[1] < left[3]
    )


def write_provenance(
    path: str | Path,
    *,
    source_url: str,
    script_name: str,
    bbox_wgs84: Box,
    crs: str,
    http_status: int | None = None,
    row_count: int | None = None,
    config_sha256: str | None = None,
    root: str | Path | None = None,
) -> Path:
    """Write a provenance sidecar beside a data file and return its path."""
    record = {
        "source_url": source_url,
        "http_status": http_status,
        "fetch_utc": datetime.now(UTC).isoformat(),
        "sha256": file_sha256(path),
        "row_count": row_count,
        "bbox_wgs84": list(bbox_wgs84),
        "crs": crs,
        "git_commit": current_commit(root),
        "config_sha256": config_sha256,
        "script_name": script_name,
    }
    output = ensure_parent(sidecar_path(path))
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")
    return output


def read_provenance(path: str | Path) -> dict[str, Any]:
    """Read and validate the provenance sidecar for a data file."""
    sidecar = sidecar_path(path)
    if not sidecar.exists():
        msg = f"Missing provenance sidecar: {sidecar}"
        raise FileNotFoundError(msg)

    record = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        msg = f"Provenance sidecar must contain an object: {sidecar}"
        raise ValueError(msg)

    require_keys(record, REQUIRED_FIELDS)
    current = file_sha256(path)
    if record["sha256"] != current:
        msg = (
            f"Data file does not match its provenance sidecar: {path} "
            f"(sidecar {record['sha256']}, current {current})"
        )
        raise ValueError(msg)
    return record


def tracked_data_files(root: str | Path | None = None) -> list[Path]:
    """List data files that require a provenance sidecar."""
    files: list[Path] = []
    for name in TRACKED_DIRECTORIES:
        directory = data_path(name, root=root)
        if not directory.exists():
            continue
        files.extend(
            path
            for path in sorted(directory.rglob("*"))
            if path.is_file()
            and path.name not in IGNORED_NAMES
            and not path.name.endswith(SIDECAR_SUFFIX)
        )
    return files
