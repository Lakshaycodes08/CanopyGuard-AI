# CanopyGuard-AI

[![CI](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml)

CanopyGuard-AI measures the spatial scale and temporal baseline at which open
satellite time series recover airborne-LiDAR-measured canopy height change,
and tests whether that signal supports maintenance prioritization on
transmission corridor spans.

The project is built as a reproducible research pipeline, not an application. Each stage reads files from disk and writes documented outputs that can be rerun independently.

New to the project, remote sensing, or machine learning? Start with
[`docs/PROJECT_FROM_SCRATCH.md`](docs/PROJECT_FROM_SCRATCH.md).

## Research goal

The goal is a defensible journal paper. The predeclared research question,
hypotheses, baselines, and evaluation rules are in
[`reports/research_design.md`](reports/research_design.md). The current
manuscript direction is:

> Detectability limits of open optical time series for canopy height change, benchmarked against repeat airborne LiDAR in power-line corridors.

## Data roles

- Sonoma County 2013, 2022 and 2023 airborne LiDAR: target and independent
  truth. The 2022 and 2023 pair is one year apart and measures the detection
  noise floor.
- Sentinel-2 from 2017 and Landsat 8 from 2013: temporal predictors.
- USGS 3DEP: terrain predictors and site quality.
- Sonoma vegetation map: alliance stratification.
- GEDI: independent cross-check, not a training target.
- California Energy Commission transmission lines: span construction and
  aggregation context only.

LiDAR never enters model features. `tests/test_truth_isolation.py` fails the
build if a feature or model module imports the LiDAR package or references a
truth path.

## Pipeline

```text
LiDAR epochs -> matched CHMs -> co-registration -> noise floor -> truth
Sentinel-2 + Landsat + terrain -> composites -> texture -> features
truth + features -> growth model -> residual model -> detectability surface
                                                   -> product benchmark
                                                   -> span ranking -> figures
```

Every arrow is a file under `data/interim` or `data/processed`. Root data directories are present in git with `.gitkeep` files, but real data is ignored by git and should be tracked with DVC.

## Dependency strategy

Two conda environments. `environment.yml` is the working environment: data
assembly, modelling, evaluation, figures and tests. It runs on a laptop and
has no point-cloud dependency.

`environment-lidar.yml` is used only for the step that turns LiDAR point
clouds into canopy height rasters. It carries PDAL and GDAL. That step reads
USGS 3DEP cloud-optimised point clouds over HTTPS by bounding box, so no
point-cloud file is downloaded, and it is normally run on a hosted notebook
rather than a laptop. Its outputs are small rasters consumed by the working
environment.

```powershell
conda env create -f environment.yml
conda activate canopyguard-ai
python -m pytest
```

Do not add a second dependency source unless there is a concrete reason. A local `.venv` may exist on one machine for temporary execution, but it is ignored and is not the project setup path.

## Checks

On Windows:

```powershell
conda activate canopyguard-ai
.\scripts\check.ps1
npm audit
```

On systems with Make:

```bash
make check
npm audit
```

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

```powershell
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

```powershell
python scripts/check_text_hygiene.py
```


## Teammate setup

New contributors should follow `CONTRIBUTING.md`. The short version is:

```powershell
git clone https://github.com/Lakshaycodes08/CanopyGuard-AI.git
cd CanopyGuard-AI
conda env create -f environment.yml
conda activate canopyguard-ai
.\scripts\check.ps1
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
