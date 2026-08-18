# CanopyGuard-AI

[![CI](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/Lakshaycodes08/CanopyGuard-AI/actions/workflows/ci.yml)

CanopyGuard-AI predicts where vegetation near power lines is likely to become risky, then helps prioritize trimming using satellite data, LiDAR validation, machine learning, risk scoring, and optimization.

The project is built as a reproducible research pipeline, not an application. Each stage reads files from disk and writes documented outputs that can be rerun independently.

## Research goal

The goal is a defensible journal paper. An international journal is preferred if the validation is strong enough. The current manuscript direction is:

> Data-driven vegetation risk forecasting and maintenance prioritization near power-line corridors using satellite time series, LiDAR validation, and optimization.

## Data roles

- HIFLD: corridor context only.
- Sentinel-2: temporal signal.
- GEDI: sparse canopy reference.
- LiDAR 3DEP: validation truth.

LiDAR should stay out of model features unless a specific experiment explicitly justifies otherwise. It is the main independent validation source.

## Pipeline

```text
HIFLD corridor context
Sentinel-2 time series       -> features -> forecasting -> risk -> scheduling -> figures
GEDI sparse reference
LiDAR validation truth       -> evaluation
```

Every arrow is a file under `data/interim` or `data/processed`. Root data directories are present in git with `.gitkeep` files, but real data is ignored by git and should be tracked with DVC.

## Dependency strategy

`environment.yml` is the canonical environment file. Use conda because the project will need geospatial packages such as GDAL, PDAL, rasterio, and related compiled dependencies.

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

`make data`, `make features`, `make forecast`, `make risk`, and `make schedule` are placeholders until the first real data source and study area are selected.

## DVC

DVC is initialized in this repository. The remote is intentionally not configured yet because storage has not been chosen.

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
