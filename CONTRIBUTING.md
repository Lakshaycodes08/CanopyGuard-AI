# Contributing to CanopyGuard-AI

This project is a Python research pipeline. Keep setup boring and reproducible.

## First-time setup

`pyproject.toml` is the canonical dependency source. Every working
dependency ships a wheel, so no compiler and no conda are required.

```bash
git clone https://github.com/Lakshaycodes08/CanopyGuard-AI.git
cd CanopyGuard-AI
uv venv --python 3.11 --seed
source .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest
```

`python -m venv .venv` and `pip install -e ".[dev]"` work identically if uv is
not installed. After pulling updates, rerun the install command to pick up
dependency changes.

The `models` extra adds SciPy, scikit-learn and LightGBM for the modelling
stage. LightGBM needs an OpenMP runtime on macOS, so install that extra only
when the modelling stage begins.

`environment-lidar.yml` is a separate conda environment carrying PDAL and
GDAL. It is used only for the step that turns LiDAR point clouds into canopy
height rasters, which normally runs on a hosted notebook.

## Expected folders after clone

These folders are tracked with placeholders, so a fresh clone should have them:

- `configs/`
- `data/raw/`
- `data/interim/`
- `data/processed/`
- `notebooks/`
- `paper/`
- `reports/`
- `reports/figures/`
- `scripts/`
- `src/canopyguard/`
- `tests/`

Real data files inside `data/` are ignored by git. Use DVC once a storage remote is chosen.

## Local checks before pushing

```bash
source .venv/bin/activate
make check
npm audit
```

On Windows without Make, `scripts/check.ps1` runs the same steps.

## DVC

DVC is initialized, but no remote is configured yet. Do not commit raw data or large model artifacts. After storage is chosen, set the remote with:

```bash
dvc remote add -d storage <remote-url>
```

## Branch workflow

1. Create a branch from `main`.
2. Keep changes small and scoped.
3. Run local checks.
4. Open a pull request.
5. Wait for CI and review before merging.

## Research integrity

Do not add tools or prompts that hide AI assistance, evade detection, strip required provenance, or make authorship misleading. AI assistance must be disclosed according to the target venue policy.
