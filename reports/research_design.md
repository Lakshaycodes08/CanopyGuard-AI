# CanopyGuard-AI research design

Locked: 2026-09-22. No data acquired and no model fitted at lock time.

## Decision

Status: PRE-DATA DESIGN LOCKED

This document fixes the primary question, hypotheses, data roles, baselines,
splits, metrics, and claim rules before any result exists. Thresholds that
require empirical calibration are listed as pending and are calibrated from
training data only.

## Primary research question

At what spatial aggregation scale and temporal baseline do open optical
satellite time series recover airborne-LiDAR-measured canopy height change in
Mediterranean-climate mixed forest, and is that recovery sufficient to
prioritise maintenance on transmission corridor spans?

The contribution is a measured detectability boundary and an open evaluation
protocol. It is not a claim of first-ever vegetation detection, growth
forecasting, risk assessment, or maintenance optimisation.

## Why the target is change and not a one-year-ahead height

Quality-filtered GEDI RH98 in steep mixed forest has a single-shot error
standard deviation of 6 to 10 m. Published annual height increment for the
mapped Sonoma alliances is 0.075 to 0.61 m. The ratio of label error to
annual signal is between 10 to 1 and 213 to 1.

Decomposing a one-year-ahead height target gives a canopy height variance of
order 144 m2, an annual growth variance of order 0.02 m2, and a label error
variance of order 49 m2. The maximum coefficient of determination attributable
to growth is 0.02 / (0.02 + 49), approximately 4e-4. Such a model would report
a coefficient of determination of 0.6 to 0.75, all of it static canopy height.

Detecting one year of mean growth at the two-sigma level requires
approximately 1,695 footprints per aggregation unit. GEDI density over the
study area is approximately 120 per km2 before the consensus quality filters
and of order 6 per km2 after them, giving a minimum detection unit of 3.5 to
14 km2 against a 10 m pixel of 1e-4 km2.

Airborne LiDAR canopy height change over a nine-year baseline is 0.7 to 5.5 m
against a limit of detection of 0.5 to 2.8 m depending on aggregation scale.
This is the only formulation in the available data where signal exceeds the
measurement noise floor.

## Analysis unit and target

- Prediction grid: EPSG:6339, aggregated from 10 m to 200 m per
  `configs/lidar.yaml`. Primary working scale 100 m. The upper bound is
  set by the calibration coverage described under noise floor measurement.
- Target: airborne LiDAR canopy height change `delta_h` between two epochs,
  computed from canopy height models regenerated from point clouds with one
  identical pipeline.
- Epoch pairs: 2022 to 2023 (1 year), 2013 to 2022 (9 years), 2013 to 2023
  (10 years). The 2007 epoch is admitted for conifer alliances only and only
  if it passes the epoch screen.
- Predictors: Sentinel-2 L2A seasonal composites 2017 onward, Landsat 8
  Collection 2 seasonal composites 2013 onward, multi-scale neighbourhood
  statistics, 3DEP terrain, vegetation alliance, fire and disturbance status.
- Corridor geometry: approximate context and aggregation only, never
  survey-grade clearance truth.

## Noise floor measurement

The 2022 and 2023 acquisitions are one year apart at 21.51 and 21.32 points
per square metre. True one-year growth is small and low-variance relative to
expected measurement error, so the distribution of their difference over
stable cells estimates the measurement error directly:

```
sigma_n(s) = NMAD[ delta_h(2022 -> 2023, s) ]
LoD95(s)   = 1.96 * sigma_n(s)
```

The spread is the normalised median absolute deviation, which is insensitive
to the disturbance tail. The plain standard deviation is reported alongside
it; the two diverging is itself a finding. LoD95 is the 95 percent limit only
where the difference is Gaussian, which the measured decay exponent tests.

This replaces literature estimates of the limit of detection with a
site-measured value. It is computed before any model is fitted.

The two acquisitions are separate 3DEP work units that abut rather than
overlap. Their 1 km delivery tile grids are offset, so the area carrying both
epochs is a seam at most 507 m wide and about 51 km2 in total, established by
intersecting the per-file bounds in the two source manifests. No square of
750 m or more lies wholly inside both acquisitions anywhere in the region, and
the same holds for every other pair of 3DEP work units that touches the study
area. Calibration therefore runs on 250 m tiles drawn from the co-covered
seam, the ladder is measured to 200 m, and coarser scales are extrapolated
from the fitted decay exponent and reported as extrapolated.

A manifest bound is the box of a delivered file's points, not its flown
polygon, so 51 km2 is an upper bound and tiles are admitted again on the
coverage of the built surfaces. A scale enters the gate and the decay fit only
once its pooled cell count reaches the configured minimum, because a spread
estimated from a handful of cells carries no information.

The seam extends beyond the study area. Measurement error is a property of the
sensors and terrain, not of the study boundary, so calibrating outside the
boundary is valid provided the strata match. A seam is also the worst geometry
either acquisition has, so the floor measured there is an upper bound on the
floor of interior coverage and is reported as one. Stratification of the
sample by vegetation group, slope band and canopy height class, and the check
on stratum coverage, are pending.

The horizontal offset between two acquisitions is a property of the pair, and
a 250 m tile spans too narrow a range of aspect to resolve it. One offset is
solved from every tile at once and applied to all of them. Its horizontal part
is applied to the canopy height grids; its vertical part belongs to the
terrain alone, because a canopy height is a difference taken inside one epoch
and its datum has already cancelled.

The 2023 and 2023 pair of CA_NorthCoastRanges_2_B23 and CA_SolanoCounty_1_A23
carries no true growth. It is run as a control, so that a residual offset
between epochs separates a pipeline fault from a real or seasonal change.

## Hypotheses

### H1: error decay

`sigma_n(s)` decreases with aggregation scale more slowly than the inverse
square root of the cell count, because measurement error is spatially
correlated. Falsified if the fitted decay exponent equals 0.5 within its
confidence interval at every scale.

### H2: detectability boundary

There exists a scale and temporal baseline at which true canopy change exceeds
`LoD95`. The boundary is located and reported. Falsified if no available
combination clears the limit of detection.

### H3: optical skill

After conditioning on vegetation alliance, start height and terrain site
quality through a fitted height-increment model, Sentinel-2 and Landsat
features reduce the mean absolute error of the residual increment. Supported
only when the paired spatial-block bootstrap interval for the difference lies
below zero. Falsified if the interval includes zero at every operational
scale.

### H4: product recovery

Existing global canopy height products, differenced across epochs, do not
recover airborne LiDAR change above `LoD95` at the measured scales, which run
to 200 m. Falsified if any product recovers change above the limit at span
scale.

### H5: ranking value

Span ranking by predicted change achieves higher recall at 10 percent of
ranked corridor length than random, cyclic, current-height-first, static-risk,
span-length and distance-to-conductor allocation. Falsified if the interval on
the difference includes zero against any of the six.

### H6: growth-rate consistency

Per-alliance one-year height increments measured from the 2022 to 2023 pair
agree with one ninth of the 2013 to 2022 increment and with the fitted
height-increment curve, within stated confidence intervals. Disagreement
beyond those intervals localises a pipeline fault and is reported as such.

H1, H2 and H6 are measurements and return a result regardless of outcome. H3,
H4 and H5 can each return null.

## Data roles

| Source | Role | Prohibited use |
| --- | --- | --- |
| Sonoma 2013, 2022, 2023 airborne LiDAR | Target and independent truth | Any model feature |
| Sentinel-2 Level-2A | Seasonal predictors from 2017 | Tile cloud percentage as a substitute for pixel masking |
| Landsat 8 Collection 2 | Seasonal predictors from 2013 | Unharmonised mixing with Sentinel-2 in one feature block |
| USGS 3DEP | Terrain predictors and site quality | Substituting for a co-registration check |
| Sonoma vegetation map | Alliance stratification and growth-model grouping | Assuming species purity at 10 m |
| GEDI02_A Version 2 | Independent cross-check and gap fill | Training target |
| CAL FIRE, MTBS, Landsat change | Disturbance status | Treating absence from one source as proof of stability |
| CEC transmission lines | Span construction and aggregation | Engineering clearance or causation claims |

Truth isolation is enforced in continuous integration by
`tests/test_truth_isolation.py`, which fails if any feature or model module
imports the LiDAR package or references a truth path.

## Model protocol

Two stages.

Stage 1 is a mechanical growth model using no satellite data. A
generalised algebraic difference form with a Chapman-Richards base function is
fitted per vegetation alliance on stable cells, predicting height increment
from start height, elapsed interval and terrain-derived site quality.
Alliances with insufficient stable sample are pooled to the physiognomic group
and the pooling is recorded.

Stage 2 predicts the residual of Stage 1 from satellite and texture features.
The reported scientific quantity is the incremental error reduction of Stage 2
over Stage 1.

The start-height anchor is the median of the eight neighbouring cells,
excluding the centre. The centre cell's start height appears in the target
with a negative sign, so using it as a feature induces spurious correlation
through shared measurement error. The centre-anchor variant is reported as a
sensitivity and the difference quantifies the artifact.

Residuals are bimodal, with a growth mode and a disturbance-loss mode, so a
unimodal Gaussian likelihood is not used. Two heads are fitted: a binary head
for the structure-loss event below the negative limit of detection, and
quantile heads at 0.05, 0.25, 0.50, 0.75 and 0.95. Intervals are calibrated by
split conformal and by group-conditional conformal on disturbance status and
height decile, with empirical coverage reported per stratum.

Model capacity is bounded by the number of spatially independent blocks, not
the number of cells. Limits are in `configs/forecasting.yaml`.

## Validation protocol

Three regimes, all reported.

1. Design-based. A simple random sample of cells is withheld permanently
   before modelling. Because truth is wall to wall over the processed
   footprint, this is an unbiased estimate of map accuracy.
2. Spatial block. Block size is selected from the practical range of the
   variogram of out-of-fold residuals, not of the target, floored at 500 m.
   Blocks are assigned to folds systematically so each fold is spatially
   dispersed.
3. Leave-one-fire-out. Each mapped fire perimeter is withheld in turn. Fold
   count is small and the resulting intervals are wide.

Area of applicability is computed per fold. Folds whose test cells exceed the
training dissimilarity quantile are flagged as extrapolation.

Confidence intervals on the error difference between two models come from a
paired bias-corrected and accelerated bootstrap that resamples whole blocks.
Resampling individual cells understates the interval on autocorrelated
residuals by approximately the square root of the cells per block.

## Baselines

Regression: global mean, global median, start-height ring isotonic fit, and
the Stage 1 growth model.

Ranking: random, cyclic by time since last inspection, current-height-first,
static risk from fire-threat tier and terrain, span length alone, and distance
to conductor alone. Span length is included because longer spans contain more
trees and a ranker that does not beat it has no value.

## Ablations

| ID | Isolates |
| --- | --- |
| A1 | Fire, by refitting on unburned cells with a buffer |
| A2 | Spectral fire detection, by adding burn severity to Stage 1 |
| A3 | Species encoded through phenology, by per-alliance centring and leave-one-alliance-out |
| A4 | Terrain, by a terrain-only baseline |
| A5 | Topographic illumination correction |
| A6 | View geometry, by single-orbit refit and orbit permutation |
| A7 | Spatial autocorrelation, by comparing the three validation regimes |
| A8 | Anchor artifact, ring against centre |
| A9 | Anchor dominance, by an anchor-free Stage 2 |
| A10 | Static mapping posing as change modelling, by temporal shuffle |
| A11 | Predictor chronology, Sentinel-2 alone against Sentinel-2 with Landsat |
| A12 | Co-registration, by recomputing change under one-pixel shifts |
| A13 | Point density, by comparing decimated and non-decimated pipelines |
| A14 | Spatial structure masquerading as signal, by replacing the satellite block with a matched Gaussian random field |

A10 and A14 are blocking. Both run before the remaining ablations. If the
temporal shuffle does not degrade error, the model carries no temporal
information. If the matched random field reproduces the satellite gain, H3 is
an artifact. Either outcome is reported as the result.

## Evaluation outputs

- Regression: mean absolute error primary; root mean squared error, signed
  bias and coefficient of determination secondary. Reported by height class,
  vegetation class, disturbance status and slope band.
- Ranking: recall at 10 percent of ranked corridor length primary, reported
  absolutely and as lift over the cyclic baseline. Secondary are the
  normalised partial area under the gain curve to 20 percent, precision at 1,
  2 and 10 percent, area under the precision-recall curve reported alongside
  prevalence, inspection burden per true positive found, and Spearman rank
  correlation.
- Calibration: reliability diagrams, expected calibration error, Brier
  decomposition, and conformal coverage per stratum.
- Cost: expected cost avoided as a sensitivity sweep over the ratio of miss
  cost to inspection cost from 10 to 10,000. No absolute currency figure is
  reported, because unit costs are not available to this study.
- Every experiment records the config hash, seed, metrics, data hashes and
  commit.

## Falsification and claim limits

The primary claim fails if the detectability boundary cannot be located, if
the satellite contribution does not survive the temporal shuffle and matched
random field controls, or if apparent improvement disappears under spatial
blocking. A useful negative result is reported as such.

No result from this design establishes regulatory clearance, tree-failure
causation, wildfire causation, or utility-grade safety certification.
Satellite-derived canopy height at 10 m carries an error of approximately 6 m,
several times the 1.22 m clearance threshold binding these voltage classes in
the High Fire-Threat District, so no span may be declared compliant or
non-compliant from this product. No reduction in outages, ignitions or cost is
claimed, because no outage or work-order records are available. Hazard trees
are not identified, because their structural and species attributes are not
observed. NERC FAC-003-4 binds lines at 200 kV and above, so only the 230 kV
lines here fall in its scope; the 60 and 115 kV lines are governed by CPUC
General Order 95 and Public Resources Code 4293.

## Pending decisions requiring data

- Admission of the 2007 epoch, from the epoch screen.
- Final spatial block size, from training residuals only.
- Sample tile count, from the measured effective sample size.
- Whether the co-covered seam carries canopy at all, from the height
  distribution of the built surfaces.
- Whether any acquisition pair with wide co-coverage exists, which would
  extend the measured ladder above 200 m.
- Whether the open fire-incident join carries enough events to report.
- Target journal and its disclosure policy.
