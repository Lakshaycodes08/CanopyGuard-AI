# AGENTS.md - Coding rules for CanopyGuard-AI

This file tells any AI coding assistant and any human contributor how to write
and organize code in this repository. Read it before writing or changing code.
If a request conflicts with these rules, follow the rules and say so.

## 0. Philosophy

Write the smallest, clearest code that correctly does the job, and put it in the
right place. Code here exists to produce trustworthy research results, not to
impress. Prefer boring, readable code over clever code.

## 1. Write like a careful human, not a generator

- Simplest thing that works. A plain function beats a class. A class beats a
  framework. Do not add layers for the future.
- YAGNI. Build only what the current task needs. No speculative options, config
  flags, or abstractions that have a single caller.
- Small units. A function does one thing and stays around 40 lines max. A file
  stays under around 300 lines. Split by responsibility when it grows past that.
- Shallow nesting. Max around 3 levels. Use early returns and guard clauses.
- Name for meaning. Use `canopy_height`, not `ch2` or `tmp`. A good name removes
  the need for a comment.
- Comment WHY, not WHAT. Explain a non-obvious decision or scientific
  assumption. Never narrate what the code plainly says.
- No dead code. Delete unused and commented-out code. Git remembers. No
  decorative banners, ASCII art, or emoji in source.
- One obvious way. Match the style already in the file. Do not introduce a
  second pattern for a job the repo already solves one way.
- Use plain ASCII in project prose unless a technical term requires otherwise.
  Do not use em dashes, smart quotes, invisible Unicode, emoji, or decorative
  characters.

## 2. Put code in the right place

- Ingestion: `src/canopyguard/data/`. One module per source. Input is config
  bbox plus dates. Output is a file in `data/interim/`.
- Feature building: `src/canopyguard/features/`.
- Forecasting: `src/canopyguard/forecasting/`.
- Risk scoring: `src/canopyguard/risk/`.
- Optimizer: `src/canopyguard/scheduling/`.
- Plots and dashboards: `src/canopyguard/viz/`.
- Shared helpers:
  - `config.py` loads and validates configs.
  - `io.py` owns paths and read/write helpers.
  - `utils.py` owns seeds and small shared helpers.
- Do not scatter path strings or config parsing across modules.
- `scripts/` holds thin entrypoints only. Parse args, call one library function,
  and exit. No real logic in scripts.
- `notebooks/` are exploration only and are never imported by the package.
  Anything worth keeping graduates into `src/`.

## 3. No hardcoding

- Study area, dates, thresholds, model settings, and paths come from
  `configs/*.yaml`, loaded through `config.py`.
- Never hardcode a bbox, date, threshold, path, or magic number inside a
  function.
- Need a new setting? Add it to the relevant config with a sensible default.

## 4. Reproducibility

- Seed everything through `utils.set_seeds`, covering `random`, `numpy`, and
  `torch` when those packages are available.
- Call `set_seeds` at the start of every experiment entrypoint.
- Use time-based splits only. Train on the past, test on the future. Never
  shuffle time-series rows across the train/test boundary.
- Include a check that no test timestamp precedes any training timestamp.
- Every stage output is a documented file, such as GeoTIFF, GeoParquet, or
  Parquet, so stages are decoupled and independently rerunnable.
- DVC is initialized in this repo. `dvc.yaml` defines the stage graph once real
  data exists. `dvc repro` must be able to regenerate outputs.
- Log every run with params, metrics, and git commit. A result that cannot be
  reproduced does not count.

## 5. Data hygiene

- Never commit data. Root `data/` contains tracked `.gitkeep` placeholders only.
  Real data is gitignored and should be DVC-tracked.
- Do not commit `.tif`, `.laz`, `.parquet`, credentials, tokens, or secrets.
- Keep the four sources in their roles:
  - LiDAR is validation truth.
  - GEDI is sparse reference.
  - Sentinel-2 is temporal signal.
  - HIFLD is approximate corridor context, not engineering truth.
- Do not merge sources into one undocumented feature blob.

## 6. Scientific integrity

- The risk score is a research prioritization, not a regulatory clearance or
  safety certification. State this in docstrings and outputs.
- Verify at source. Any fact, constant, or growth-rate value used in code traces
  to `reports/claims_log.md` with its source.
- AI suggestions are leads to verify, not truth.
- Disclose AI assistance in the paper according to the venue policy.
- Do not add code, tools, prompts, or steps meant to hide provenance or bypass
  publisher AI-use policies.
- Do not add AI-provenance-removal, detector-evasion, or authorship-masking
  tools to this repository.

## 7. Dependencies

- Add a dependency only when a task needs it.
- Prefer the standard library or something already in `environment.yml`.
- `environment.yml` is the canonical dependency source. Use conda for project
  work because the geospatial stack will rely on compiled packages.
- Do not maintain a second dependency truth. Local `.venv` folders are allowed
  only as ignored, machine-local scratch environments.
- A new heavy dependency, such as PyTorch or PDAL, must be justified in the PR.
- No ad-hoc `pip install` into a shared environment.

## 8. Project-local skills and Node files

- `.agents/skills` is intentionally tracked only for paper-writing and literature
  review workflows that are safe to expose in a public research repository.
- `package.json` and `package-lock.json` exist only to anchor `npm audit` to this
  repository. This is not a Node application.
- `node_modules/` must stay ignored and must never be committed.

## 9. Testing

- Every non-trivial function in `src/` gets at least one `pytest` test with a
  tiny fixture.
- Test tricky logic such as time splits, spatial alignment, scoring, and config
  validation.
- Tests are fast and offline. No live calls to NASA, GEE, HIFLD, or other remote
  data providers.

## 10. Do not build

Do not add microservices, Kubernetes, Airflow, a feature store, model registry,
custom ORM, database, plugin system, premature GPU code, or a config framework
beyond YAML. If one becomes necessary, open an issue with a concrete reason
first.

## 11. Definition of done

Every change should satisfy these checks:

1. Does one thing in the right module.
2. Is config-driven with no hardcoded project settings.
3. Is ruff clean and formatted.
4. Has a relevant test when logic changes.
5. Is reproducible, seeded, and respects time splits.
6. Commits no data and no secrets.
7. Explains what and why in plain English.
