# CanopyGuard-AI from scratch

Technical onboarding. Read `reports/research_design.md` first for the current
design. This document explains the concepts and the pipeline that implement
it.

## 1. Problem

Given an airborne LiDAR survey at `t0` and open data available up to `t0`,
forecast which transmission-corridor spans will carry vegetation within
clearance distance by `t0 + k` years, and rank spans better than cyclic,
current-height-first and random allocation.

The forecast and span ranking are the spine. Label-quality measurement (the
LiDAR noise floor and the detectability of canopy change) is a supporting
result inside methods, not the primary contribution.

## 2. Why the target is canopy height change

Canopy height is easy to map and hard to map well. Growth is the opposite: it
is the quantity of operational interest and it is small.

Annual height increment for the mapped Sonoma alliances is 0.075 to 0.61 m.
Quality-filtered GEDI RH98 in steep mixed forest has a single-shot error
standard deviation of 6 to 10 m. A one-year-ahead height model fitted against
GEDI would report a good coefficient of determination consisting entirely of
static canopy height, because the growth component contributes at most about
4e-4 of the explainable variance.

Airborne LiDAR change over a nine-year baseline is 0.7 to 5.5 m against a
limit of detection of 0.5 to 2.8 m depending on aggregation. That is the only
formulation where signal exceeds the noise floor, and it is why LiDAR-derived
canopy height change is the label the forecast heads are trained against.
Block-mean height change is a label-quality statement, not the operational
target: clearance risk is carried by upper-percentile and local-maximum
canopy height near conductors, not by the 30 m block mean. The full
arithmetic is in `reports/research_design.md`.

## 3. The measuring instrument

The 2022 and 2023 LiDAR acquisitions are one year apart at 21.51 and 21.32
points per square metre. One year of true growth is small relative to the
expected measurement error, so the spread of their difference over stable
cells estimates that error directly.

```
sigma_n(s) = sd[ delta_h(2022 -> 2023, s) ]
LoD95(s)   = 1.96 * sigma_n(s)
```

Everything downstream is compared against `LoD95(s)`. It is measured, not
assumed.

## 4. Data roles

| Source | Role |
| --- | --- |
| Sonoma airborne LiDAR 2013, 2022, 2023 | Target and independent truth. Never a feature |
| Sentinel-2 L2A, 2017 onward | Seasonal optical predictors at 10 m |
| Landsat 8 Collection 2, 2013 onward | Seasonal predictors covering the pre-Sentinel window |
| USGS 3DEP | Terrain and site quality |
| Sonoma vegetation map | Alliance stratification for the growth model |
| CAL FIRE, MTBS, Landsat change | Disturbance status |
| GEDI02_A Version 2 | Independent cross-check only |
| CEC transmission lines | Span construction |

Sentinel-2 begins in 2017 and the 2013 to 2022 label window begins in 2013, so
45 percent of that window is unobserved by Sentinel-2. Landsat covers it and
is kept as a separate feature block so its contribution is ablatable.

## 5. Concepts

**Raster and pixel.** A grid of values with a geographic transform. A 10 m
pixel covers 10 by 10 m on the ground.

**Band.** One spectral channel. Sentinel-2 bands used here are B02, B03, B04,
B08 at 10 m and B05, B06, B07, B8A, B11, B12 at 20 m. SWIR (B11, B12) and red
edge (B05 to B07) outrank greenness for canopy structure.

**CRS.** Coordinate reference system. Working CRS is EPSG:6339, NAD83(2011)
UTM zone 10N, in metres. Vertical datum is NAVD88.

**Resampling.** Bilinear for reflectance, nearest for categorical layers such
as the scene classification mask.

**Alignment.** Every raster shares one origin, resolution and transform.
Misalignment between LiDAR epochs is the dominant controllable error: on a 30
degree slope, 1 m of horizontal shift produces 0.58 m of apparent vertical
change, comparable to nine years of oak growth.

**Cloud masking.** Applied per pixel from the scene classification layer.
Scene-level cloud percentage is a catalogue filter, never a pixel guarantee.

**Composite.** A per-pixel reduction over a time window. Seasonal medians and
percentiles handle cloud gaps without imputation.

**DSM, DTM, CHM.** Digital surface model is the top of returns. Digital
terrain model is the ground. Canopy height model is their difference.

**LoD95.** Limit of detection at 95 percent confidence for a difference
between two measurements. Change below it is not distinguishable from error.

**Saturation.** Optical signal stops responding to height above roughly 25 to
30 m canopy. Sonoma redwood and Douglas-fir reach 30 to 70 m. Spatial texture,
not spectral value, is what carries information above saturation.

## 6. Study setup

- Bounding box: west -122.90, south 38.475, east -122.74, north 38.82.
- Processing scope: a 60 m corridor buffer plus 40 stratified 1 km tiles,
  roughly 64 km2. Not the full 533 km2 box.
- Point clouds are read by bounding box from USGS 3DEP cloud-optimised point
  clouds on AWS. No point-cloud file is downloaded. The LiDAR-to-raster step
  runs in the `canopyguard-lidar` environment on a hosted notebook; every
  other step runs in the working environment on a laptop.
- The 2013 acquisition is served as three 3DEP resources (Sonoma A2, A3 and
  A4), which are read together and merged for each tile.
- Optical composites are built server side in Google Earth Engine and
  exported as rasters. The STAC path in `configs/ingestion.yaml` is the
  fallback for contributors without Earth Engine.
- Aggregation ladder: 10, 20, 30, 50, 100, 200 m.
- Temporal baselines: 1 year (2022 to 2023), 9 years (2013 to 2022), 10 years
  (2013 to 2023).
- Every required result runs on CPU.

## 7. Pipeline

1. **Epoch screen.** Admit a LiDAR epoch only if density, scan angle, season,
   ground classification and declared datum all pass. Recorded per epoch.
2. **Fetch.** Point clouds for admitted epochs over the processing scope. Only
   the tile manifest is version-controlled; the clouds are regenerable.
3. **Harmonise.** Common horizontal and vertical frame, scan angle clipped,
   noise classes dropped, then every epoch decimated to the density of the
   sparsest admitted epoch. Decimation is not optional: denser returns find
   canopy apexes more often and manufacture apparent growth.
4. **CHM.** One identical pipeline for every epoch. Same ground algorithm,
   same height-above-ground method, same pit-free construction, same clamp.
5. **Co-register.** Per 1 km tile, against the 2022 reference, using
   ground-classified points on low slope.
6. **Aggregate and difference.** Produce the scale ladder and the epoch-pair
   differences.
7. **Noise floor.** Measure `sigma_n(s)` and `LoD95(s)` from the one-year
   pair over stable cells. Gate: proceed only if the mean one-year change lies
   between minus the detection limit and a physically plausible growth, and
   `sigma_n` falls with scale within its sampling error.
8. **Predictors.** Seasonal composites with topographic correction and
   view-angle normalisation, vegetation indices, multi-scale neighbourhood
   statistics, terrain, fire and disturbance status, corridor spans.
9. **As-of feature store.** LiDAR t0 structure, terrain, optical history to
    t0, climate, vegetation type, fire history, keyed by cell and cutoff
    date. The builder refuses any source observed after its cutoff.
10. **Forecast heads.** A disturbance hazard head and a conditional growth
    head, described in section 8.
11. **Product benchmark.** Existing free canopy height products against the
    same truth, both as differenced baselines and as candidate features.
12. **Span ranking.** Span prioritisation by predicted encroachment
    probability and expected time, against cyclic, current-height-first,
    random and span-length allocation.

## 8. Models

Two heads, both conditioned on the as-of feature set at t0:

- A disturbance hazard head, predicting the probability that a cell or span
  crosses the clearance-relevant threshold by `t0 + k`.
- A conditional growth head, quantile regression on height change given no
  disturbance, at quantiles 0.05, 0.25, 0.50, 0.75 and 0.95.

Growth and disturbance-loss residuals are bimodal, so a single Gaussian
likelihood is not used. The start-height anchor for the growth head is the
ring median of the eight neighbours, excluding the centre cell, because the
centre cell's own height appears in the target and its measurement error
would induce spurious correlation if also used as a feature.

Model capacity is bounded by the number of spatially independent blocks, not
the number of cells. Limits are in `configs/forecasting.yaml`.

## 9. Validation

Spatial block cross-validation, with block size from the practical range of
the variogram of out-of-fold residuals and a buffer between train and test
blocks sized from the same residual variogram. One region is held out
entirely from every fold, for a fully independent generalisation estimate.

An out-of-time check runs on the 2022 to 2023 pair, the one interval where
both a t0-only feature set and the realised outcome exist.

Confidence intervals on model and ranking differences come from a paired
tile-block bootstrap that resamples whole blocks. Resampling individual cells
understates the interval by roughly the square root of the cells per block.

Two ablations are blocking and run before the others. The temporal shuffle
permutes the as-of cutoff date; if error does not degrade, the model carries
no temporal information and is not forecasting. The matched random field
replaces the satellite block with a Gaussian random field of the same spatial
autocorrelation; if it reproduces the gain, the gain is spatial structure, not
signal.

## 10. Metrics

Cell level: mean absolute error on the growth head, and quantile coverage for
both heads, reported by height class, vegetation class, disturbance status
and slope band.

Span level: recall at 1, 2 and 10 percent of ranked corridor length for
"vegetation within the clearance envelope by t1", primary, reported
absolutely and as lift over the cyclic baseline, against current-height-first,
random and span-length allocation. Secondary are the partial area under the
gain curve, area under the precision-recall curve reported with prevalence,
and inspection burden per true positive.

Mean absolute error in metres is a validation quantity, not a headline. A 6 m
height error against a 1.22 m clearance threshold gives a discrimination area
under the curve of about 0.56, so no clearance decision can rest on cell-level
height error alone; the span-ranking evaluation is what the claim rests on.

## 11. Completed

- Phase 0 feasibility, all six scientific gates.
- Research design reframed to a span-level encroachment forecast, 2026-09-24.
- Verified literature comparison matrix.
- Sentinel-2 catalogue manifest, 458 Level-2A items, tile 10SEH, DVC-recorded.
- Reflectance scaling, clear-pixel compositing, clear-observation counts.
- Provenance sidecars enforced on every data file.
- Truth isolation enforced in continuous integration.
- Evaluation core in `src/canopyguard/evaluation`: metrics, paired spatial
  block bootstrap, variogram-driven blocking, detectability surface.

- Measured noise floor, 2022-2023 pair, 52 admitted tiles: NMAD 0.10 m at
  30-50 m, LoD95 about 0.20 m, sigma at the 100 m reference scale 0.092 m
  (extrapolated), bias -0.08 m, gate passed.
- Long-baseline pair 2013-2022, 30 tiles: bare-ground NMAD 0.073 m, median
  canopy change +0.84 to +0.95 m over 8.96 years, 87 to 92 percent of canopy
  cells above LoD95 at 10 to 100 m.

## 12. Not completed

See the `Not completed` list in `MEMORY.md`, which is the live record.

## 13. Where code goes

Rules are in `AGENTS.md`. Summary:

| Directory | Contents |
| --- | --- |
| `src/canopyguard/data/` | One ingestion module per source |
| `src/canopyguard/lidar/` | Truth pipeline. Never imported by feature or model code |
| `src/canopyguard/features/` | Composites, indices, texture, terrain, assembly |
| `src/canopyguard/evaluation/` | Metrics, blocking, bootstrap, detectability |
| `src/canopyguard/forecasting/` | Growth model, residual model, conformal |
| `src/canopyguard/risk/` | Spans and ranking |
| `scripts/` | Thin entrypoints. No logic |
| `configs/` | Every threshold, path and setting |

No bbox, date, threshold, path or magic number appears inside a function.

## 14. Git, DVC, configuration

Git holds code, configs and small text records. DVC holds derived rasters, the
analysis table and model artifacts. Raw point clouds are not tracked; they are
regenerated from a tracked tile manifest recording per-tile URL and checksum.

Every run records the config hash, seed, data hashes and commit. Every number
that reaches the manuscript has a row in `reports/claims_log.md`.

## 15. Failure modes to prevent

- Reporting a static height map as a change model. The temporal shuffle
  catches it.
- Mistaking spatial structure for signal. The matched random field catches it.
- Differencing the delivered CHM rasters. The 2013 and 2022 products use
  different geoids, units and generation pipelines. Regenerate both.
- Skipping decimation. Density mismatch manufactures growth.
- Skipping co-registration. Slope converts horizontal shift into vertical
  change.
- Random cross-validation. Neighbouring cells leak.
- Bootstrapping cells instead of blocks. Intervals come out an order of
  magnitude too narrow.
- Letting LiDAR into features. The guard test fails the build.
- Treating a catalogue query count as data in hand.

## 16. Source-of-truth documents

| File | Holds |
| --- | --- |
| `reports/research_design.md` | Current question, hypotheses, protocol, claim limits |
| `MEMORY.md` | Current phase, decisions, immediate next action |
| `reports/data_feasibility.md` | Phase 0 evidence |
| `reports/phase1_data_protocol.md` | Growth evidence and disturbance screen |
| `reports/literature_review.md` | Comparison matrix and novelty position |
| `reports/claims_log.md` | Every paper-bound number and its source |
| `AGENTS.md` | Coding rules |
| `configs/` | Every operative parameter |
