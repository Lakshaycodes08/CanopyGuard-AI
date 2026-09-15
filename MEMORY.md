# CanopyGuard-AI project memory

Last updated: 2026-09-15

## Purpose

This file is the short, persistent project handoff. Update it after every phase
gate, major scientific decision, or change to the immediate next action. It is
not a replacement for detailed evidence, configs, the claims log, or Git
history.

Do not record passwords, API keys, credentials, raw data, or unverified
scientific claims here.

## Current status

- Active phase: Phase 1, data-foundation work.
- Completed phase: Phase 0.
- Phase 0 decision: GO.
- Phase 1 literature review: `reports/literature_review.md` contains a verified
  15-study core matrix and a provisional, explicitly falsifiable gap. It is not
  yet a systematic review.
- Phase 1 growth and disturbance protocol: three mapped alliances have cited,
  age-dependent growth evidence; the independent disturbance screen combines
  CAL FIRE, MTBS, annual Landsat change, and visual audit.
- First ingestion target: Sentinel-2 MGRS tile 10SEH, which contains reference
  corridor feature 671. The config-driven, DVC-recorded STAC stage retained 458
  Level-2A items across 2017-2022 with all 11 required assets.
- Pre-data research design: `reports/research_design.md` locks the primary
  question, hypotheses, time and spatial splits, baselines, ablations, metrics,
  and falsification criteria before model results exist.
- Pre-access compute plan: `reports/hpc_readiness.md` requests at least 300 GiB
  of shared persistent plus scratch capacity and lists the exact NSUT scheduler,
  GPU, storage, network, and quota details still needed.
- Offline cube foundation: metadata-driven reflectance scaling, monthly
  clear-pixel compositing, clear-observation counts, and a storage estimator are
  implemented with small synthetic tests.
- Beginner technical handoff: `docs/PROJECT_FROM_SCRATCH.md` explains the data,
  geospatial concepts, ML design, completed work, quality gates, compute plan,
  team roles, and full post-access workflow from first principles.
- Target: complete the minimum publishable study and manuscript submission
  package by 2026-10-31. Journal acceptance is not controlled by the project
  and may occur later.
- Research goal: produce a defensible journal publication, with the software
  serving the experiments and evidence.
- Immediate next action: obtain the NSUT access details recorded in
  `reports/hpc_readiness.md`, configure shared storage and DVC, then build the
  masked 10 m tile-10SEH cube and report clear-observation counts.

## Research direction

CanopyGuard-AI will test whether affordable satellite time series, sparse GEDI
height measurements, ecological growth information, and independent airborne
LiDAR validation can support future vegetation-risk prioritization near
transmission corridors and improve maintenance scheduling over simple
baselines.

The research question and evaluation protocol are predeclared. The novelty gap
remains provisional and must be narrowed if the systematic search finds an
earlier equivalent evidence chain.

The risk score is a research prioritization aid. It is not a regulatory
clearance, engineering survey, or safety certification.

## Confirmed study area

- Name: northern Sonoma candidate
- CRS: EPSG:4326
- Bounding box: west -122.90, south 38.475, east -122.74, north 38.82
- Study dates: 2017-01-01 through 2022-12-31
- Config: `configs/study_area.yaml`
- Status in config: confirmed

## Phase 0 evidence

All six scientific gates pass:

1. Corridor and vegetation: 41 published operational overhead PG&E source
   features intersect the box at 60, 115, or 230 kV. The geometry is approximate
   context, not engineering truth.
2. Repeat LiDAR: the Sonoma County 2013 and 2022 canopy-height services both
   returned valid data for all 1,271,808 cells in the shared feasibility grid.
3. GEDI: 63,942 quality-filtered 2019-2022 footprints span 54 acquisition dates
   and 54 orbits. There are 29,866 footprints in exact study-period MTBS fire
   perimeters and 2,132 in the southern comparison box.
4. Sentinel-2: the catalogue returned 139 to 320 Level-2A scenes per year for
   2017-2022 at the feasibility cloud threshold.
5. Comparison forest: the southern comparison sub-box contains about 751
   hectares under the persistent-canopy screen and no intersecting CAL FIRE
   perimeter. Phase 1 must still screen other disturbances.
6. Independent check: 38 CAL FIRE perimeters intersect the study box, including
   Tubbs, Pocket, Kincade, and Walbridge. Overlap cannot establish causation.

Detailed evidence and limitations are in `reports/data_feasibility.md`.
Paper-bound claims and sources are in `reports/claims_log.md`.

## Data-source roles

- Sentinel-2: dense temporal signal.
- GEDI: sparse canopy-height reference.
- Sonoma County 2013 and 2022 canopy-height products: independent validation
  truth after alignment and quality control.
- California Energy Commission transmission lines: approximate corridor
  context. This replaces HIFLD as the primary Phase 0 corridor source.
- CAL FIRE and MTBS fire perimeters: independent spatial consistency checks.
- Verified forestry literature: ecological growth priors.

Do not merge these sources into an undocumented feature blob. Each source must
keep its stated scientific role.

## Accounts and reproducibility

- NASA Earthdata: confirmed.
- Google Earth Engine: confirmed, noncommercial Community Tier.
- OpenTopography: confirmed registered academic user with data access.
- Environment specification: `environment.yml`.
- Automated tests: 35 passed on 2026-09-15 after the cube and split additions;
  Ruff and text-hygiene checks also passed.
- Fixed seeds and chronological split validation: implemented.
- DVC: the `sentinel2_manifest` stage and lockfile are active; no remote is
  selected.
- Real data must remain out of Git and be tracked through DVC.

## Not completed

- Systematic literature search and final defensible novelty statement
- Raster asset ingestion and masked one-tile cube
- Pixel-level Sentinel-2 cloud masking and clear-observation counts
- LiDAR quality control and analysis-ready alignment
- Disturbance-screened comparison samples
- Reproducible aligned data cube
- Height model, forecasting benchmark, and temporal evaluation
- Risk map, scheduling optimizer, ablations, significance tests, and error
  analysis
- Dashboard, final figures, manuscript results, and journal submission
- DVC remote, experiment tracker, and confirmed NSUT HPC details

## Repository checkpoint

Phase 0 evidence, the confirmed study-area configuration, and this memory file
belong in one dedicated checkpoint. Preserve unrelated user changes and review
every future diff before committing it.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-12 | Target a submission-ready study by 2026-10-31 | The user requested an October finish; the scope will prioritize the minimum defensible experiment and treat optional deep learning, dashboard work, and extra study areas as stretch goals. |
| 2026-09-12 | Phase 0 GO | The exact box passed all six scientific gates and required account access was confirmed. |
| 2026-09-12 | Use the refined northern Sonoma box | The earlier small candidate lacked a mapped fire event for the planned independent check. |
| 2026-09-12 | Use CEC lines as primary corridor context | The current California source was directly verifiable; the handbook's HIFLD plan is retained only as background. |
| 2026-09-12 | Keep LiDAR as validation truth | Independent validation is required for a defensible paper and must not leak into ordinary model features. |
| 2026-09-14 | Narrow the provisional novelty claim | Prior work already covers LiDAR growth forecasting, satellite corridor risk, temporal Sentinel-2/GEDI height mapping, and trimming optimization separately. The defensible candidate is the open evidence chain joining free time series, independent repeat-LiDAR validation, ecological-prior ablation, and constrained scheduling. This remains provisional until the Phase 1 review is complete. |
| 2026-09-15 | Use age-aware growth evidence only as a weak prior | Published height growth varies strongly with species, age, site, and competition. A universal annual-growth constant would not be defensible. |
| 2026-09-15 | Select MGRS tile 10SEH for the first cube | The already-checked reference corridor feature 671 falls in this tile, allowing the first data cube to stay tied to verified corridor vegetation. |
| 2026-09-15 | Keep disturbance screening independent | CAL FIRE, MTBS, and Landsat trajectory evidence will define stable and challenge subsets without treating Sentinel-2 forecast inputs as unquestioned truth. |
| 2026-09-15 | Lock the pre-data research design | Declaring hypotheses, baselines, splits, metrics, and falsification rules before training reduces result-driven methodological changes. |
| 2026-09-15 | Start with CPU baselines | Median, persistence, Random Forest, and histogram gradient boosting must establish value before any heavy or GPU model is justified. |
| 2026-09-15 | Move data work to shared NSUT infrastructure | The estimated raw and working footprint is unsuitable for routine laptop use; shared storage also gives teammates one reproducible data location. |

## Update rule

At the end of each meaningful task:

1. Change the current phase or immediate next action when needed.
2. Add only verified results and link the detailed evidence file.
3. Move resolved items out of `Not completed`.
4. Add important scientific decisions to the decision log.
5. Keep this file short enough to read at the start of a work session.
