#!/usr/bin/env bash
# Provision the lidar environment on a Colab VM and measure the noise floor.
# No kernel restart, so this runs headlessly under colab exec.
set -euo pipefail

REPO="${REPO:-https://github.com/Lakshaycodes08/CanopyGuard-AI.git}"
BRANCH="${BRANCH:-phase1/reconciliation-and-pipelines}"
TILES="${TILES:-40}"
WORK="${WORK:-/content/CanopyGuard-AI}"
ENV_PREFIX="${ENV_PREFIX:-/content/lidar-env}"

if [ ! -d "$WORK" ]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$WORK"
fi
cd "$WORK"

if [ ! -x /content/bin/micromamba ]; then
  mkdir -p /content/bin
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xvj -C /content --strip-components=1 bin/micromamba
  mv /content/micromamba /content/bin/micromamba 2>/dev/null || true
fi
MAMBA=/content/bin/micromamba
[ -x "$MAMBA" ] || MAMBA=$(command -v micromamba)

if [ ! -d "$ENV_PREFIX" ]; then
  "$MAMBA" create -y -p "$ENV_PREFIX" -c conda-forge \
    python=3.11 pdal python-pdal rasterio pyproj numpy pyyaml
fi

PY="$ENV_PREFIX/bin/python"
"$PY" -c "import pdal, rasterio; print('pdal', pdal.__version__)"
PYTHONPATH=src "$PY" scripts/run_noise_floor.py --tiles "$TILES" --out /content/truth
