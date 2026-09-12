# CanopyGuard-AI project memory

Last updated: 2026-09-12

## Purpose

This file is the short, persistent project handoff. Update it after every phase
gate, major scientific decision, or change to the immediate next action. It is
not a replacement for detailed evidence, configs, the claims log, or Git
history.

Do not record passwords, API keys, credentials, raw data, or unverified
scientific claims here.

## Current status

- Active phase: Phase 1 is ready to begin.
- Completed phase: Phase 0.
- Phase 0 decision: GO.
- Target: complete the minimum publishable study and manuscript submission
  package by 2026-10-31. Journal acceptance is not controlled by the project
  and may occur later.
- Research goal: produce a defensible journal publication, with the software
  serving the experiments and evidence.
- Immediate next action: begin the structured Phase 1 literature review and
  pilot data ingestion in parallel.

## Research direction

CanopyGuard-AI will test whether affordable satellite time series, sparse GEDI
height measurements, ecological growth information, and independent airborne
LiDAR validation can support future vegetation-risk prioritization near
transmission corridors and improve maintenance scheduling over simple
baselines.

This wording is provisional. Phase 1 must lock the research question, novelty
gap, hypotheses, baselines, and evaluation protocol after reviewing the recent
literature.

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
- Automated tests: 21 passed on 2026-09-12.
- Fixed seeds and chronological split validation: implemented.
- DVC: initialized, but `dvc.yaml` has no real stages and no remote is selected.
- Real data must remain out of Git and be tracked through DVC.

## Not completed

- Phase 1 literature comparison and defensible novelty gap
- Final research question and hypotheses
- Cited ecological growth-rate table
- Real data ingestion modules
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

## Update rule

At the end of each meaningful task:

1. Change the current phase or immediate next action when needed.
2. Add only verified results and link the detailed evidence file.
3. Move resolved items out of `Not completed`.
4. Add important scientific decisions to the decision log.
5. Keep this file short enough to read at the start of a work session.
