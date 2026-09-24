# CanopyGuard-AI

[![CI](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml)

CanopyGuard-AI forecasts, from an airborne LiDAR survey at t0 and open data
available up to t0, which transmission-corridor spans will carry vegetation
within clearance distance by t0 + k years, and ranks spans against cyclic,
current-height-first and random allocation.

The project is built as a reproducible research pipeline, not an application. Each stage reads files from disk and writes documented outputs that can be rerun independently.

New to the project, remote sensing, or machine learning? Start with
[`docs/PROJECT_FROM_SCRATCH.md`](docs/PROJECT_FROM_SCRATCH.md).

## Research goal

The goal is a defensible journal paper. The research question, hypotheses,
baselines, and evaluation rules are in
[`reports/research_design.md`](reports/research_design.md) and are revised as
evidence accumulates. The current manuscript direction is:

> Span-level forecasting of vegetation encroachment on transmission corridors from airborne LiDAR and open earth-observation data, ranked against operational allocation baselines.

## Data roles

- Sonoma County 2013, 2022 and 2023 airborne LiDAR: label source and
  label-quality truth. The 2022 and 2023 pair is one year apart and measures
  the detection noise floor.
- Landsat 5/7/8 history to the forecast cutoff: as-of temporal predictors.
- USGS 3DEP: terrain predictors and site quality.
- LANDFIRE / Sonoma vegetation map: vegetation type stratification.
- TerraClimate: climate normals and climatic water deficit.
- CAL FIRE FRAP, MTBS: disturbance history before the cutoff.
- GEDI: independent cross-check, not a training target.
- OpenStreetMap power lines, cross-checked against California Energy
  Commission transmission lines: span construction and voltage.

No source dated after its forecast cutoff enters a feature for that cutoff.
`tests/test_truth_isolation.py` fails the build if a feature or model module
imports the LiDAR package or references a truth path at or after its own
epoch.

## Pipeline

```text
LiDAR epochs -> matched CHMs -> co-registration -> label-quality noise floor
LiDAR t0 structure + terrain + Landsat history + climate + fire + veg type
                                        -> as-of feature store (per cutoff)
feature store -> disturbance hazard head + conditional growth head
              -> product benchmark
              -> corridor spans -> span ranking -> output table and map
```

Every arrow is a file under `data/interim` or `data/processed`. Root data directories are present in git with `.gitkeep` files, but real data is ignored by git and should be tracked with DVC.

## Dependency strategy

`environment.yml` is the canonical dependency source and is what CI installs
from. Use conda because the geospatial stack relies on compiled packages.

A plain virtual environment also works for day-to-day development, since
every dependency in `pyproject.toml` ships a wheel and needs no compiler:

```bash
uv venv --python 3.11 --seed
source .venv/bin/activate
uv pip install -e ".[dev]"
make check
```

`python -m venv` and `pip` work identically if uv is not installed. Keep
`pyproject.toml` a subset of `environment.yml`, not an independent source: a
dependency belongs in `environment.yml` first.

Optional extras: `.[models]` adds SciPy, scikit-learn and LightGBM for the
modelling stage. LightGBM needs an OpenMP runtime on macOS, so install that
extra only when the modelling stage begins.

`environment-lidar.yml` is separate and carries PDAL and GDAL. It is used
only for the step that turns LiDAR point clouds into canopy height rasters.
That step reads USGS 3DEP cloud-optimised point clouds over HTTPS by bounding
box, so no point-cloud file is downloaded, and it normally runs on a hosted
notebook rather than a laptop. Its outputs are small rasters consumed by the
working environment.

```bash
uv venv --python 3.11 --seed
source .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest
```

Do not add a second dependency source unless there is a concrete reason. A local `.venv` may exist on one machine for temporary execution, but it is ignored and is not the project setup path.

## Checks

```bash
source .venv/bin/activate
make check
npm audit
```

On Windows without Make, `scripts/check.ps1` runs the same steps.

The confirmed study area is northern Sonoma County. The first DVC stage records
the Sentinel-2 tile-10SEH catalogue manifest. Processing is scoped to a
corridor buffer plus a stratified tile sample, roughly 64 km2, and every
required result runs on CPU.

## DVC

DVC is initialized in this repository. The remote is intentionally not
configured yet because the NSUT storage target and scheduler details are
pending. The access checklist and capacity estimate are in
[`reports/hpc_readiness.md`](reports/hpc_readiness.md).

After choosing storage, configure it with a command such as:

```bash
dvc remote add -d storage <remote-url>
```

Do not commit raw data. Use DVC for large data and model artifacts.

## Project-local skills and Node files

Two project-local paper skills are intentionally tracked under `.agents/skills`:

- `research-paper-writer`
- `firecrawl-research-papers`

`package.json` and `package-lock.json` are present only to anchor `npm audit` to this repository. CanopyGuard-AI is still a Python research project and has no Node runtime dependency. `node_modules/` is ignored and must not be committed.

Use the tracked skills for paper structure and literature discovery. Do not add tools that hide AI assistance, bypass a publisher policy, strip required provenance, or make authorship misleading. AI assistance must be disclosed according to the target venue policy.

## Text hygiene

Project prose should stay plain ASCII unless a technical term requires otherwise. Avoid em dashes, smart quotes, invisible Unicode, emoji, and decorative characters. This rule exists to keep code, CSVs, diffs, and manuscript files clean and reproducible. It must not be used as a provenance-removal or disclosure-evasion workflow.

Run:

```bash
python scripts/check_text_hygiene.py
```


## Teammate setup

New contributors should follow `CONTRIBUTING.md`. The short version is:

```bash
git clone https://github.com/Lakshaycodes08/CanopyGuard-AI.git
cd CanopyGuard-AI
uv venv --python 3.11 --seed
source .venv/bin/activate
uv pip install -e ".[dev]"
make check
```

The expected empty data folders are tracked with `.gitkeep` files, so a fresh clone includes `data/raw`, `data/interim`, and `data/processed`.

## Repository layout

```text
configs/                 YAML settings
data/                    ignored data workspace with tracked placeholders
src/canopyguard/         Python package
scripts/                 thin command-line entrypoints
tests/                   fast offline tests
reports/                 claims log and figures
paper/                   manuscript files
```
