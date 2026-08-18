# Contributing to CanopyGuard-AI

This project is a Python research pipeline. Keep setup boring and reproducible.

## First-time setup

Use conda. `environment.yml` is the canonical dependency source.

```powershell
git clone https://github.com/Lakshaycodes08/CanopyGuard-AI.git
cd CanopyGuard-AI
conda env create -f environment.yml
conda activate canopyguard-ai
python -m pytest
```

If the environment already exists after pulling updates, refresh it:

```powershell
conda activate canopyguard-ai
conda env update -f environment.yml --prune
```

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

On Windows:

```powershell
conda activate canopyguard-ai
.\scripts\check.ps1
npm audit
```

On Linux or macOS:

```bash
conda activate canopyguard-ai
make check
npm audit
```

## DVC

DVC is initialized, but no remote is configured yet. Do not commit raw data or large model artifacts. After storage is chosen, set the remote with:

```powershell
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
