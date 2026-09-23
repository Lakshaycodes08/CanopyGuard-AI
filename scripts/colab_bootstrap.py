from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = os.environ.get("REPO", "https://github.com/Lakshaycodes08/CanopyGuard-AI.git")
BRANCH = os.environ.get("BRANCH", "feat/lidar-truth-pipeline")
TILES = os.environ.get("TILES", "40")
RUN_TESTS = os.environ.get("RUN_TESTS", "1") != "0"
WORK = Path(os.environ.get("WORK", "/content/CanopyGuard-AI"))
ENV_PREFIX = Path(os.environ.get("ENV_PREFIX", "/content/lidar-env"))
OUT = Path(os.environ.get("OUT", "/content/truth"))
MAMBA_URL = "https://micro.mamba.pm/api/micromamba/linux-64/latest"
MAMBA = Path("/content/bin/micromamba")
PROJ_DATA = ENV_PREFIX / "share" / "proj"


def prefix_environment() -> dict[str, str]:
    """Environment for the prefix interpreter, which is never activated.

    PROJ and GDAL find their data through these variables. Calling the
    interpreter by path skips activation, so they must be set here.
    """
    return {
        **os.environ,
        "PROJ_DATA": str(PROJ_DATA),
        "PROJ_LIB": str(PROJ_DATA),
        "GDAL_DATA": str(ENV_PREFIX / "share" / "gdal"),
        "PYTHONUNBUFFERED": "1",
    }


def run(
    step: str,
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Run a command, streaming its output through this process's stdout.

    A child writing straight to its own stdout does not reach a notebook cell,
    so every line is read back and reprinted here.
    """
    print(f"\n=== {step} ===\n$ {' '.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line.rstrip(), flush=True)
    code = process.wait()
    if code != 0:
        raise SystemExit(f"step '{step}' failed with exit code {code}")


def fetch_repo() -> None:
    if (WORK / ".git").exists():
        run("fetch repo", ["git", "fetch", "--depth", "1", "origin", BRANCH], WORK)
        run("checkout", ["git", "checkout", "-B", BRANCH, f"origin/{BRANCH}"], WORK)
    else:
        clone = ["git", "clone", "--branch", BRANCH, "--depth", "1", REPO, str(WORK)]
        run("clone", clone)


def fetch_micromamba() -> None:
    if MAMBA.exists():
        print(f"\n=== micromamba ===\ncached at {MAMBA}", flush=True)
        return
    print(f"\n=== micromamba ===\ndownloading {MAMBA_URL}", flush=True)
    MAMBA.parent.mkdir(parents=True, exist_ok=True)
    archive = Path("/content/micromamba.tar.bz2")
    urllib.request.urlretrieve(MAMBA_URL, archive)  # noqa: S310
    with tarfile.open(archive, "r:bz2") as bundle:
        member = bundle.getmember("bin/micromamba")
        member.name = MAMBA.name
        bundle.extract(member, MAMBA.parent)
    MAMBA.chmod(0o755)
    print(f"installed {MAMBA}", flush=True)


def environment_is_complete() -> bool:
    """A half-built prefix has an interpreter but no PROJ database.

    Checking only for the interpreter lets an interrupted build be reused, and
    every reprojection then fails with an unhelpful PROJ error.
    """
    interpreter = ENV_PREFIX / "bin" / "python"
    return interpreter.exists() and (PROJ_DATA / "proj.db").exists()


def create_environment() -> None:
    if environment_is_complete():
        print(f"\n=== environment ===\ncached at {ENV_PREFIX}", flush=True)
        return
    if ENV_PREFIX.exists():
        print("\n=== environment ===\nincomplete, rebuilding", flush=True)
        shutil.rmtree(ENV_PREFIX)
    run(
        "create environment",
        [
            str(MAMBA),
            "create",
            "-y",
            "-p",
            str(ENV_PREFIX),
            "-c",
            "conda-forge",
            "python=3.11",
            "pdal",
            "python-pdal",
            "rasterio",
            "pyproj",
            "proj",
            "proj-data",
            "numpy",
            "pyyaml",
            "pytest",
        ],
    )
    if not environment_is_complete():
        raise SystemExit(f"environment built without a PROJ database at {PROJ_DATA}")


def ensure_pytest(python: str) -> None:
    """Add pytest to a prefix built before the test step existed.

    A cached environment is otherwise reused without it and the test step
    fails on an environment that is fine for the measurement.
    """
    probe = subprocess.run(
        [python, "-c", "import pytest"],
        env=prefix_environment(),
        capture_output=True,
    )
    if probe.returncode == 0:
        return
    run(
        "install pytest",
        [
            str(MAMBA),
            "install",
            "-y",
            "-p",
            str(ENV_PREFIX),
            "-c",
            "conda-forge",
            "pytest",
        ],
    )


def main() -> int:
    print(f"branch {BRANCH}\ntiles {TILES}\noutput {OUT}", flush=True)
    fetch_repo()
    fetch_micromamba()
    create_environment()

    python = str(ENV_PREFIX / "bin" / "python")
    check = (
        "import pdal, rasterio, pyproj; print('pdal', pdal.__version__);"
        " print('crs', pyproj.CRS.from_user_input('EPSG:6339').name)"
    )
    run("verify", [python, "-c", check], env=prefix_environment())

    environment = {**prefix_environment(), "PYTHONPATH": "src"}
    if RUN_TESTS:
        ensure_pytest(python)
        run("tests", [python, "-m", "pytest", "-q"], WORK, environment)

    print("\n=== measure ===", flush=True)
    process = subprocess.Popen(
        [python, "scripts/run_noise_floor.py", "--tiles", TILES, "--out", str(OUT)],
        cwd=WORK,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line.rstrip(), flush=True)
    return process.wait()


if __name__ == "__main__":
    sys.exit(main())
