# CanopyGuard-AI from scratch

Technical onboarding. Read `reports/research_design.md` first for the locked
design. This document explains the concepts and the pipeline that implement it.

## 1. Problem

Measure the spatial aggregation scale and temporal baseline at which open
optical satellite time series recover airborne-LiDAR-measured canopy height
change in Mediterranean-climate mixed forest, then test whether that signal
supports prioritisation of transmission corridor spans.

Two halves. The detectability measurement and product benchmark form the
spine. The corridor span ranking is the applied half and is reported whatever
its outcome.

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
formulation where signal exceeds the noise floor. The full arithmetic is in
`reports/research_design.md`.

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
9. **Detectability surface.** Signal, noise, signal-to-noise ratio and
   detectable fraction over the scale and baseline grid.
10. **Models.** The ladder in section 8.
11. **Product benchmark.** Existing free canopy height products against the
    same truth, inside corridor buffers and across the tile sample.
12. **Ranking.** Span prioritisation against six allocation baselines.

## 8. Models

Stage 1 uses no satellite data. A generalised algebraic difference form with a
Chapman-Richards base function is fitted per vegetation alliance, predicting
height increment from start height, elapsed interval and terrain-derived site
quality. Height increment depends on position on the species height-age curve,
which varies sevenfold within one species, and start height is the observable
proxy for that position.

Stage 2 predicts the Stage 1 residual from satellite and texture features.
That residual is a growth anomaly, whose plausible drivers are canopy water
stress, competition, sub-threshold disturbance and recovery trajectory. The
reported scientific quantity is the error reduction of Stage 2 over Stage 1.

The start-height anchor is the ring median of the eight neighbours, excluding
the centre, because the centre cell's start height appears in the target with
a negative sign and its measurement error would induce spurious correlation.

Ladder, in order, each with a condition to proceed: global mean and median;
ring-anchor isotonic fit; Stage 1; ridge on the residual; gradient boosting on
the residual; quantile heads with conformal calibration; scale sweep; product
benchmark; span ranking. A patch convolutional model is optional and no
required result depends on it.

Model capacity is bounded by the number of spatially independent blocks, not
the number of cells. Limits are in `configs/forecasting.yaml`.

## 9. Validation

Three regimes, all reported.

- **Design-based.** A random sample withheld permanently before modelling.
  Truth is wall to wall over the processing scope, so this is an unbiased
  estimate of map accuracy. Most canopy height studies cannot do this.
- **Spatial block.** Block size from the practical range of the variogram of
  out-of-fold residuals, floored at 500 m, folds assigned so each is
  spatially dispersed.
- **Leave-one-fire-out.** Each fire perimeter withheld in turn. Wide intervals
  by construction.

Confidence intervals on model differences come from a paired bias-corrected
and accelerated bootstrap that resamples whole blocks. Resampling individual
cells understates the interval by roughly the square root of the cells per
block.

Two ablations are blocking and run before the others. The temporal shuffle
permutes which year's composites attach to each cell; if error does not
degrade, the model carries no temporal information. The matched random field
replaces the satellite block with a Gaussian random field of the same spatial
autocorrelation; if it reproduces the gain, the gain is spatial structure, not
signal.

## 10. Metrics

Regression: mean absolute error primary, with root mean squared error, signed
bias and coefficient of determination secondary, reported by height class,
vegetation class, disturbance status and slope band.

Ranking: recall at 10 percent of ranked corridor length primary, reported
absolutely and as lift over the cyclic baseline. That budget is not arbitrary;
it matches the published boundary of a utility high-risk band. Secondary are
the partial area under the gain curve, precision at 1, 2 and 10 percent, area
under the precision-recall curve reported with prevalence, and inspection
burden per true positive.

Mean absolute error in metres is a validation quantity, not a headline. A 6 m
height error against a 1.22 m clearance threshold gives a discrimination area
under the curve of about 0.56, so no clearance decision can rest on it.

## 11. Completed

- Phase 0 feasibility, all six scientific gates.
- Locked research design.
- Verified literature comparison matrix.
- Sentinel-2 catalogue manifest, 458 Level-2A items, tile 10SEH, DVC-recorded.
- Reflectance scaling, clear-pixel compositing, clear-observation counts.
- Provenance sidecars enforced on every data file.
- Truth isolation enforced in continuous integration.
- Evaluation core in `src/canopyguard/evaluation`: metrics, paired spatial
  block bootstrap, variogram-driven blocking, detectability surface.

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
| `reports/research_design.md` | Locked question, hypotheses, protocol, claim limits |
| `MEMORY.md` | Current phase, decisions, immediate next action |
| `reports/data_feasibility.md` | Phase 0 evidence |
| `reports/phase1_data_protocol.md` | Growth evidence and disturbance screen |
| `reports/literature_review.md` | Comparison matrix and novelty position |
| `reports/claims_log.md` | Every paper-bound number and its source |
| `AGENTS.md` | Coding rules |
| `configs/` | Every operative parameter |
