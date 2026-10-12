from __future__ import annotations

import ast
import re
from importlib.util import resolve_name
from pathlib import Path

import pytest

from canopyguard.config import load_config
from canopyguard.features.lidar import select_lidar_feature_epoch
from canopyguard.io import project_root

SOURCE = project_root() / "src" / "canopyguard"
FEATURE_PACKAGES = ("features", "forecasting", "risk")
GATE_MODULE = "canopyguard.features.lidar"
GATE_FUNCTION = f"{GATE_MODULE}.select_lidar_feature_epoch"
RAW_LIDAR_MODULES = (
    "canopyguard.lidar",
    "canopyguard.data.lidar",
    "canopyguard.data.lidar_fetch",
)
TRUTH_FILE_NAME = re.compile(r"(^|/)(labels|change|label_quality)_\d{4}-\d{4}")
TRUTH_PATHS = ("processed/truth", "interim/lidar", "processed/lidar")


@pytest.fixture
def lidar_config():
    return load_config("configs/lidar.yaml")


def test_2013_lidar_can_be_a_feature_for_2022(lidar_config):
    survey = select_lidar_feature_epoch(
        lidar_config,
        "2013",
        target_epoch="2022",
        prediction_cutoff="2013-11-26",
    )
    assert survey["name"] == "2013"


def test_2022_lidar_can_be_a_feature_for_2023(lidar_config):
    survey = select_lidar_feature_epoch(
        lidar_config,
        "2022",
        target_epoch="2023",
        prediction_cutoff="2022-11-11",
    )
    assert survey["name"] == "2022"


@pytest.mark.parametrize(
    ("epoch", "target_epoch", "cutoff"),
    [("2013", "2022", "2013-11-25"), ("2022", "2023", "2013-11-26")],
)
def test_lidar_acquired_after_cutoff_cannot_be_a_feature(
    lidar_config, epoch, target_epoch, cutoff
):
    with pytest.raises(ValueError, match="ends after prediction cutoff"):
        select_lidar_feature_epoch(
            lidar_config, epoch, target_epoch=target_epoch, prediction_cutoff=cutoff
        )


@pytest.mark.parametrize("cutoff", ["2022-09-13", "2023-01-01"])
def test_cutoff_cannot_reach_target_survey(lidar_config, cutoff):
    with pytest.raises(ValueError, match="must precede target LiDAR survey"):
        select_lidar_feature_epoch(
            lidar_config, "2013", target_epoch="2022", prediction_cutoff=cutoff
        )


def test_target_survey_cannot_be_its_own_feature(lidar_config):
    with pytest.raises(ValueError, match="target LiDAR survey cannot be a feature"):
        select_lidar_feature_epoch(
            lidar_config,
            "2022",
            target_epoch="2022",
            prediction_cutoff="2013-11-26",
        )


@pytest.mark.parametrize(
    ("epoch", "target_epoch"),
    [("2024", "2022"), ("2013", "2024")],
)
def test_unknown_lidar_epoch_cannot_be_used(lidar_config, epoch, target_epoch):
    with pytest.raises(ValueError, match="Unknown LiDAR epoch"):
        select_lidar_feature_epoch(
            lidar_config,
            epoch,
            target_epoch=target_epoch,
            prediction_cutoff="2014-01-01",
        )


def test_lidar_without_an_end_date_cannot_be_a_feature(lidar_config):
    del lidar_config["epochs"][0]["end"]
    with pytest.raises(ValueError, match="needs a valid end date"):
        select_lidar_feature_epoch(
            lidar_config,
            "2013",
            target_epoch="2022",
            prediction_cutoff="2014-01-01",
        )


def test_target_without_a_start_date_cannot_be_used(lidar_config):
    del lidar_config["epochs"][1]["start"]
    with pytest.raises(ValueError, match="needs a valid start date"):
        select_lidar_feature_epoch(
            lidar_config,
            "2013",
            target_epoch="2022",
            prediction_cutoff="2014-01-01",
        )


def test_prediction_cutoff_must_be_a_full_date(lidar_config):
    with pytest.raises(ValueError, match="prediction_cutoff must use YYYY-MM-DD"):
        select_lidar_feature_epoch(
            lidar_config,
            "2013",
            target_epoch="2022",
            prediction_cutoff="2013",
        )


def _modules() -> list[Path]:
    return [
        path
        for package in FEATURE_PACKAGES
        for path in sorted((SOURCE / package).rglob("*.py"))
        if path != SOURCE / "features" / "lidar.py"
    ]


def _under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _raw_lidar(name: str) -> bool:
    return any(_under(name, module) for module in RAW_LIDAR_MODULES)


def _import_violations(node: ast.Import | ast.ImportFrom, package: str) -> list[str]:
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
        return [name for name in names if _raw_lidar(name) or _under(name, GATE_MODULE)]

    module = (
        resolve_name(f"{'.' * node.level}{node.module or ''}", package)
        if node.level
        else node.module or ""
    )
    if _raw_lidar(module):
        return [module]
    names = [f"{module}.{alias.name}" for alias in node.names]
    return [
        name
        for name in names
        if _raw_lidar(name)
        or (name == GATE_MODULE)
        or (_under(name, GATE_MODULE) and name != GATE_FUNCTION)
    ]


def _attribute_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_attribute_name(node.value)}.{node.attr}"
    return ""


def _truth_reference(value: str) -> bool:
    value = value.replace("\\", "/").lower()
    return (
        value == "label_archive"
        or any(path in value for path in TRUTH_PATHS)
        or bool(TRUTH_FILE_NAME.search(value))
        or any(module in value for module in RAW_LIDAR_MODULES)
        or (value.startswith(GATE_MODULE) and value != GATE_FUNCTION)
    )


def _violations(tree: ast.AST, package: str) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.extend(_import_violations(node, package))
        elif isinstance(node, ast.Attribute):
            name = _attribute_name(node)
            if _raw_lidar(name) or name == GATE_MODULE:
                found.append(name)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"data_path", "Path"}:
                parts = [
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ]
                if _truth_reference("/".join(parts)):
                    found.append("/".join(parts))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _truth_reference(node.value)
        ):
            found.append(node.value)
    return found


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.name)
def test_feature_and_model_code_uses_only_the_lidar_gate(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module = "canopyguard." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
    assert not _violations(tree, module.rpartition(".")[0]), path


@pytest.mark.parametrize(
    "source",
    [
        "from canopyguard.lidar.change import measure_pair",
        "from canopyguard.data import lidar",
        "from ..lidar import change",
        "from canopyguard.features import lidar",
        "import canopyguard.features.lidar",
        "from canopyguard.features.lidar import other_reader",
        "path = 'data/processed/labels_2013-2022_unique.npz'",
        "path = data_path('processed', 'labels_2013-2022_unique.npz')",
        "path = data_path('interim', 'lidar', '2013.tif')",
        "path = data_path('processed', 'truth')",
        "path = config['label_archive']['unique']",
        "importlib.import_module('canopyguard.features.lidar')",
    ],
)
def test_scan_rejects_direct_lidar_or_truth_access(source):
    assert _violations(ast.parse(source), "canopyguard.features")


def test_scan_allows_importing_the_checked_selector():
    source = "from canopyguard.features.lidar import select_lidar_feature_epoch"
    assert not _violations(ast.parse(source), "canopyguard.features")
