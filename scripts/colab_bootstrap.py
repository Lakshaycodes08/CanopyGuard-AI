from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = os.environ.get("REPO", "https://github.com/Lakshaycodes08/CanopyGuard-AI.git")
BRANCH = os.environ.get("BRANCH", "feat/lidar-truth-pipeline")
WORK = Path(os.environ.get("WORK", "/content/CanopyGuard-AI"))


def run(command: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    if WORK.exists():
        run(["git", "fetch", "--depth", "1", "origin", BRANCH], cwd=WORK)
        run(["git", "checkout", "-B", BRANCH, f"origin/{BRANCH}"], cwd=WORK)
    else:
        run(["git", "clone", "--branch", BRANCH, "--depth", "1", REPO, str(WORK)])
    run(["bash", str(WORK / "scripts" / "colab_bootstrap.sh")], cwd=WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
