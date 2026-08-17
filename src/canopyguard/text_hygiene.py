from __future__ import annotations

from pathlib import Path

DISALLOWED_CHARS = {
    "\u200b": "zero width space",
    "\u200c": "zero width non-joiner",
    "\u200d": "zero width joiner",
    "\ufeff": "byte order mark",
    "\u2014": "em dash",
    "\u2013": "en dash",
    "\u2018": "left single quote",
    "\u2019": "right single quote",
    "\u201c": "left double quote",
    "\u201d": "right double quote",
}

TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml", ".tex", ".txt"}
SKIP_DIRS = {".git", ".agents", ".dvc", ".pytest_cache", ".ruff_cache", ".venv"}


def find_disallowed_chars(text: str) -> list[tuple[int, str, str]]:
    """Return line number, character, and reason for disallowed Unicode."""
    findings: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for char in line:
            reason = DISALLOWED_CHARS.get(char)
            if reason:
                findings.append((line_number, char, reason))
    return findings


def iter_text_files(root: str | Path) -> list[Path]:
    """Return repository text files that should pass prose hygiene checks."""
    root_path = Path(root)
    files: list[Path] = []

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Makefile", "LICENSE"}:
            files.append(path)

    return files
