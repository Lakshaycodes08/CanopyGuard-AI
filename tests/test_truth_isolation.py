from __future__ import annotations

import ast
from pathlib import Path

import pytest

from canopyguard.io import project_root

FEATURE_PACKAGES = ("features", "forecasting", "risk")
FORBIDDEN_MODULES = ("canopyguard.lidar",)
FORBIDDEN_PATHS = ("processed/truth", "data/processed/truth")


def _modules() -> list[Path]:
    source = project_root() / "src" / "canopyguard"
    return [
        path
        for package in FEATURE_PACKAGES
        for path in sorted((source / package).rglob("*.py"))
    ]


def _imported_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.name)
def test_module_does_not_import_lidar_truth(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for name in _imported_names(tree):
        assert not name.startswith(FORBIDDEN_MODULES), f"{path}: {name}"


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.name)
def test_module_does_not_reference_truth_paths(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for fragment in FORBIDDEN_PATHS:
                assert fragment not in node.value, f"{path}: {node.value}"
