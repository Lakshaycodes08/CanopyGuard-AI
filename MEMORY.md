# CanopyGuard-AI project memory

Last updated: 2026-09-22

## Purpose

This file is the short, persistent project handoff. Update it after every phase
gate, major scientific decision, or change to the immediate next action. It is
not a replacement for detailed evidence, configs, the claims log, or Git
history.

Do not record passwords, API keys, credentials, raw data, or unverified
scientific claims here.

## Current status

- Active phase: Phase 1, airborne LiDAR truth construction.
- Completed phase: Phase 0.
- Phase 0 decision: GO.
- Target set on 2026-09-22: airborne LiDAR canopy height change across a
  ladder of aggregation scales and temporal baselines. The earlier
  one-year-ahead GEDI RH98 regression was dropped because label error exceeds
  annual growth by a factor of 10 to 213. The arithmetic is in
  `reports/research_design.md`.
- LiDAR epochs confirmed by OpenTopography catalogue query against the study
  bbox: 2007, 2011 partial, 2013, 2022, 2023. The 2022 and 2023 pair is one
  year apart at 21.51 and 21.32 points per square metre and measures the
  detection noise floor empirically. 2023 covers only the northern part of the
  study bbox, so the noise floor is calibrated on the full 2022 and 2023
  intersection and stratified to match the study area. The 2018 NoCAL
  Wildfires acquisition does not cover this bbox.
- Seven synthetic parquet files found in `data/interim` on 2026-09-22 and
  moved to `data/QUARANTINE_2026-09-22`. Their coordinates lay about 4,000 km
  from the study area and they were not produced by any script in this
  repository. No model was fitted and no result was reported from them.
- Provenance sidecars are now required on every file written to
  `data/interim` and `data/processed`, enforced by `tests/test_provenance.py`.
- Truth isolation is enforced by `tests/test_truth_isolation.py`, which fails
  if any feature or model module imports the LiDAR package or references a
  truth path.
- Evaluation core implemented and tested in `src/canopyguard/evaluation/`:
  metrics, paired spatial block bootstrap, variogram-driven blocking, and the
  detectability surface.
- LiDAR truth pipeline implemented and tested in `src/canopyguard/lidar/`:
  raster operations, Nuth and Kaab co-registration, epoch admission and
  decimation, PDAL pipeline construction, scale ladder and differencing,
  footprint and coverage probing, Entwine access, tiling and the calibration
  plan. PDAL is imported in one function, so the rest is tested without it.
  225 tests pass. No epoch has been processed yet.
- Point clouds are read by bounding box from the public 3DEP Entwine
  resources at `usgs-lidar-public`. Both noise-floor epochs are confirmed
  present: `CA_NorthernCA_1_B22` holds 95,945,998,233 points and
  `CA_NorthCoastRanges_2_B23` holds 186,415,389,199, both indexed in
  EPSG:3857. Return density computed from those counts is 21.5 and 21.3 per
  square metre, matching the catalogue. The 8.16 per square metre quoted in
  the 2023 acquisition specification is pulse density from a 0.35 m nominal
  pulse spacing, a different quantity that must not be mixed with the first.
- The LiDAR step has two entrypoints. `notebooks/01_noise_floor.ipynb` is
  interactive. `scripts/colab_bootstrap.sh` provisions the environment with
  micromamba and runs `scripts/run_noise_floor.py` headlessly, with no kernel
  restart, so it works under a non-interactive runner. The script exits
  non-zero when the gate fails.
- Gate thresholds are in `configs/lidar.yaml` under `noise_floor.gate` and are
  applied by `lidar/noise_floor.evaluate_gate`, not by the caller.
- Phase 1 literature review: `reports/literature_review.md` contains a verified
  15-study core matrix and a provisional, explicitly falsifiable gap. It is not
  yet a systematic review.
- Phase 1 growth and disturbance protocol: three mapped alliances have cited,
  age-dependent growth evidence; the independent disturbance screen combines
  CAL FIRE, MTBS, annual Landsat change, and visual audit.
- First ingestion target: Sentinel-2 MGRS tile 10SEH, which contains reference
  corridor feature 671. The config-driven, DVC-recorded STAC stage retained 458
  Level-2A items across 2017-2022 with all 11 required assets.
- Research design: `reports/research_design.md` sets out the primary
  question, hypotheses, time and spatial splits, baselines, ablations, metrics,
  and falsification criteria. Reframed 2026-09-24 from a detectability
  benchmark to a span-level encroachment forecast; nothing in the design is
  locked or pre-registered, and it is revised as evidence accumulates.
- Compute: CPU only for every required result. Two environments.
  `environment.yml` runs data assembly, modelling, evaluation, figures and
  tests on a laptop. `environment-lidar.yml` carries PDAL and GDAL and is used
  only for the LiDAR-to-raster step, normally on a hosted notebook. That step
  reads USGS 3DEP cloud-optimised point clouds by bounding box over HTTPS, so
  no point-cloud file is downloaded. Optical composites are built in Google
  Earth Engine and exported. Working footprint on the laptop is a few GiB.
  `reports/hpc_readiness.md` is retained as the record of the earlier estimate.
- Compositing foundation: metadata-driven reflectance scaling, clear-pixel
  compositing, clear-observation counts, and a storage estimator are
  implemented with small synthetic tests.
- Beginner technical handoff: `docs/PROJECT_FROM_SCRATCH.md` explains the data,
  geospatial concepts, ML design, completed work, quality gates, compute plan,
  team roles, and full post-access workflow from first principles.
- Target: a submission-ready study and manuscript package. No fixed date.
  Scope is gated on measurement, not on a calendar.
- Research goal: produce a defensible journal publication, with the software
  serving the experiments and evidence.
- Immediate next action: create the working environment and confirm the test
  suite runs. The epoch screen and the 2022 and 2023 coverage probes are done
  and recorded in `reports/lidar_epoch_screen.md`. Next is the notebook that
  reads 3DEP point clouds by bounding box over the calibration intersection,
  writes matched canopy height rasters, co-registers per tile, and produces
  the noise floor. That measurement precedes the study-area work, so a
  failure costs one notebook run. The full-area dense Sentinel-2 cube is
  cancelled.

## Research direction

CanopyGuard-AI forecasts, from an airborne LiDAR survey at t0 and open data
available up to t0, which transmission-corridor spans will carry vegetation
within clearance distance by t0 + k years, and ranks spans against cyclic,
current-height-first and random allocation. Label quality (the LiDAR noise
floor and the detectability of canopy change) is measured as a supporting
result, not the primary contribution. Existing free canopy height products
are benchmarked against the same LiDAR truth, both as baselines and as
candidate features.

The research question and evaluation protocol are in
`reports/research_design.md` and are revised as evidence accumulates. The
contribution is the span-level forecast, its ranking evaluation against
operational allocation rules, and the open evaluation protocol, not component
integration.

The risk score is a research prioritization aid. It is not a regulatory
clearance, engineering survey, or safety certification.

## Confirmed study area

- Name: northern Sonoma candidate
- CRS: EPSG:4326
- Bounding box: west -122.90, south 38.475, east -122.74, north 38.82
- Predictor dates: 2013-01-01 through 2023-12-31. Sentinel-2 from 2017,
  Landsat 8 from 2013.
- LiDAR epochs: 2013, 2022, 2023, with 2007 conditional on the epoch screen.
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
   perimeters and 2,132 in the southern comparison box. This is a Google Earth
   Engine query count under the weak Phase 0 screen, not downloaded data. No
   GEDI granule is present on disk. Under the consensus filter set in
   `configs/forecasting.yaml`, which adds night-only, full-power beams,
   sensitivity at or above 0.95, and a 30 degree slope limit, the expected
   retained count is of order 3,000 to 6,000, and the retained sample is
   biased toward shorter and less dense canopy. GEDI is therefore an
   independent cross-check in this project, not a training target.
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
- Environment specification: `pyproject.toml`, installed into a virtual
  environment. `environment-lidar.yml` is a separate conda environment for
  the PDAL step only.
- Automated tests: 35 passed on 2026-09-15 after the cube and split additions;
  Ruff and text-hygiene checks also passed.
- Fixed seeds and chronological split validation: implemented.
- DVC: the `sentinel2_manifest` stage and lockfile are active; no remote is
  selected.
- Real data must remain out of Git and be tracked through DVC.

## Not completed

- Systematic literature search and final defensible novelty statement
- Per-10 m-cell labels (mean, 95th percentile, maximum canopy height and their
  changes, loss share) over corridor tiles plus a background sample, on the
  global 10 m grid; later a crown or local-maximum layer
- As-of feature store keyed by cell and cutoff date, refusing any source
  observed after the cutoff: LiDAR t0 structure, terrain, Landsat history with
  disturbance age, climate normals and water deficit, vegetation type, fire
  perimeters before t0, NAIP
- Disturbance hazard head and conditional growth head (quantile heads)
- Corridor spans from OpenStreetMap power lines, cross-checked against the
  CEC layer for voltage, and span-level cell aggregation
- Spatial block cross-validation with a residual-variogram buffer and one
  region held out entirely; out-of-time check on the 2022-2023 pair
- Span-ranking evaluation against cyclic, current-height-first, random and
  span-length allocation, with paired tile-block bootstrap intervals
- Product benchmark and candidate-feature test using Lang et al. 2023,
  Meta/WRI and GLAD products
- Output span table and map of top-ranked spans with probability and expected
  time to encroachment
- Final figures, manuscript results, and journal submission
- DVC remote and experiment tracker

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
| 2026-09-15 | Lock the pre-data research design | Declaring hypotheses, baselines, splits, metrics, and falsification rules before training reduces result-driven methodological changes. Superseded 2026-09-24. |
| 2026-09-24 | Unlock the design and reframe from a detectability benchmark to a span-level encroachment forecast | An independent review found the retrospective Landsat model used end-of-period imagery and the outcome differences themselves, valid as attribution but not as forecast; utilities need span-level, ranked, backtested, forward-looking risk, and block-mean height change is not the clearance-relevant quantity. Full design in `reports/research_design.md`. |
| 2026-09-15 | Start with CPU baselines | Median, persistence, Random Forest, and histogram gradient boosting must establish value before any heavy or GPU model is justified. |
| 2026-09-22 | Quarantine all files in `data/interim` and add provenance and truth-isolation guards | Seven parquet files present in the pipeline input directory were synthetic and described a bounding box about 4,000 km from the study area. They were not produced by any script in the repository. |
| 2026-09-22 | Withdraw the one-year-ahead GEDI RH98 target | Label error of 6 to 10 m against annual growth of 0.075 to 0.61 m gives a maximum growth-attributable coefficient of determination of about 4e-4. Any fitted model would be a static height map. |
| 2026-09-22 | Adopt airborne LiDAR change as the target, at a ladder of scales and baselines | This is the only formulation in the available data where signal exceeds the measurement noise floor. |
| 2026-09-22 | Measure the noise floor from the 2022 and 2023 epoch pair | The two acquisitions are one year apart at 21.51 and 21.32 points per square metre. True one-year growth is negligible against their difference, so that difference estimates measurement error directly. |
| 2026-09-22 | Demote GEDI to independent cross-check | The consensus quality filter chain leaves of order 6 footprints per square kilometre and biases retention toward shorter canopy. |
| 2026-09-22 | Restore topography features, cut in the v3 plan | Slope drives GEDI error from 5.8 m below 15 degrees to 16.2 m above 35 degrees, and terrain illumination is confounded with both species and height. |
| 2026-09-22 | Make Stage 1 a fitted GADA height-increment model per vegetation alliance | Height increment depends on position on the species height-age curve, which varies sevenfold within one species. Start height is the observable proxy for that position. |
| 2026-09-22 | Build and test the evaluation core before acquiring data | A defect in the bootstrap, blocking or detectability code would corrupt every reported number. One such defect was found and fixed during this work. |
| 2026-09-15 | Move data work to shared NSUT infrastructure | The estimated raw and working footprint is unsuitable for routine laptop use; shared storage also gives teammates one reproducible data location. |

## Update rule

At the end of each meaningful task:

1. Change the current phase or immediate next action when needed.
2. Add only verified results and link the detailed evidence file.
3. Move resolved items out of `Not completed`.
4. Add important scientific decisions to the decision log.
5. Keep this file short enough to read at the start of a work session.
