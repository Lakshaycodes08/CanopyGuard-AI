from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


def _micromamba_platform() -> str:
    """Micromamba's release channel name for the machine running this script.

    Defaults assume Colab (linux-64). A native run on another OS/arch, such
    as this project's own laptop fallback, needs the matching build or the
    downloaded binary just fails to exec.
    """
    system = platform.system()
    machine = platform.machine()
    if system == "Linux":
        return "linux-aarch64" if machine in ("aarch64", "arm64") else "linux-64"
    if system == "Darwin":
        return "osx-arm64" if machine == "arm64" else "osx-64"
    raise SystemExit(f"no known micromamba build for {system}/{machine}")


REPO = os.environ.get("REPO", "https://github.com/Lakshaycodes08/CanopyGuard-AI.git")
BRANCH = os.environ.get("BRANCH", "feat/lidar-truth-pipeline")
TILES = os.environ.get("TILES", "40")
WORKERS = os.environ.get("WORKERS", "1")
RUN_TESTS = os.environ.get("RUN_TESTS", "1") != "0"
WORK = Path(os.environ.get("WORK", "/content/CanopyGuard-AI"))
ENV_PREFIX = Path(os.environ.get("ENV_PREFIX", "/content/lidar-env"))
OUT = Path(os.environ.get("OUT", "/content/truth"))
SCRIPT = os.environ.get("SCRIPT", "run_noise_floor.py")
PAIR = os.environ.get("PAIR", "")
EXTRA_ARGS = os.environ.get("EXTRA_ARGS", "")
DUMP_FILES = [name for name in os.environ.get("DUMP_FILES", "").split(",") if name]
MAMBA_URL = os.environ.get(
    "MAMBA_URL",
    f"https://micro.mamba.pm/api/micromamba/{_micromamba_platform()}/latest",
)
MAMBA = Path(os.environ.get("MAMBA_PATH", "/content/bin/micromamba"))
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
            "pandas",
            "pyyaml",
            "pytest",
        ],
    )
    if not environment_is_complete():
        raise SystemExit(f"environment built without a PROJ database at {PROJ_DATA}")


TEST_PACKAGES = ("pytest", "pandas")


def ensure_test_packages(python: str) -> None:
    """Add the test packages to a prefix built before the test step existed.

    A cached environment is otherwise reused as complete and collection fails
    on an environment that is fine for the measurement itself.
    """
    missing = [
        package
        for package in TEST_PACKAGES
        if subprocess.run(
            [python, "-c", f"import {package}"],
            env=prefix_environment(),
            capture_output=True,
        ).returncode
    ]
    if not missing:
        return
    run(
        "install test packages",
        [str(MAMBA), "install", "-y", "-p", str(ENV_PREFIX), "-c", "conda-forge"]
        + missing,
    )


def main() -> int:
    print(
        f"branch {BRANCH}\nscript {SCRIPT}\ntiles {TILES}\nworkers {WORKERS}"
        f"\noutput {OUT}",
        flush=True,
    )
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
        ensure_test_packages(python)
        run("tests", [python, "-m", "pytest", "-q"], WORK, environment)

    command = [
        python,
        f"scripts/{SCRIPT}",
        "--tiles",
        TILES,
        "--workers",
        WORKERS,
        "--out",
        str(OUT),
    ]
    if SCRIPT == "run_change.py" and PAIR:
        command += ["--pair", PAIR]
    command += EXTRA_ARGS.split()

    print("\n=== measure ===", flush=True)
    process = subprocess.Popen(
        command,
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
    code = process.wait()
    if code == 0:
        dump_outputs()
    return code


def dump_outputs() -> None:
    """Print small result files as base64, framed by grep-able markers.

    A follow-up command issued right after this long exec call returns has
    reliably hit a stale-connection error in practice, even while `colab
    status` still shows the session alive. Printing the files here instead
    puts them on the same stdout stream that already carried hours of output
    without trouble, so the caller can pull them out of its own saved log
    with no second round trip to the VM.
    """
    import base64

    for name in DUMP_FILES:
        path = OUT / name
        if not path.exists():
            print(f"=== dump {name} missing ===", flush=True)
            continue
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        print(f"=== dump {name} base64 {len(payload)} bytes ===", flush=True)
        width = 4096
        for start in range(0, len(payload), width):
            print(payload[start : start + width], flush=True)
        print(f"=== dump {name} end ===", flush=True)


if __name__ == "__main__":
    sys.exit(main())
