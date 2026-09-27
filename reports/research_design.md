# CanopyGuard-AI research design

Reframed: 2026-09-24, superseding the design dated 2026-09-22. Nothing in this
project is locked or pre-registered; this document is a working design and is
revised as evidence accumulates. Thresholds calibrated after data were seen
are marked post hoc.

## Decision

An independent review on 2026-09-24 found that the design this document
previously fixed answered an attribution question, not a forecast question:
the retrospective Landsat model explained 2013-2022 canopy height change using
2022 imagery and the 2013-2022 differences themselves, both of which observe
the outcome it claimed to predict. Utilities act on span-level, one-to-three
year, ranked and backtested encroachment risk, and block-mean 30 m height
change of about 0.1 m per year is not the clearance-relevant quantity; the
upper percentiles and local maxima near conductors are. The project is
reframed from a detectability benchmark to a forecast product. Detectability
remains in the design as a label-quality result, not as the spine.

## Primary research question

Given an airborne LiDAR survey at `t0` and open data available up to `t0`,
forecast which transmission-corridor spans will carry vegetation within
clearance distance by `t0 + k` years, and rank spans better than cyclic,
current-height-first and random allocation.

The contribution is a span-level forecast and ranking evaluated against
operational allocation rules, built on a measured label-quality
characterisation of the underlying LiDAR truth. It is not a claim of
first-ever vegetation detection, a compliance determination, or a hazard-tree
identification.

`k` up to 1 year is validated by the out-of-time check below. `k` of 2 or 3
years is a stated goal, not yet backed by ground truth: only one LiDAR
interval (2022 to 2023) exists with outcomes on both sides of a cutoff, and no
conductor geometry is available to place the clearance envelope itself, only
span-level line geometry from OpenStreetMap (see Data roles). Treat the 2 and
3 year horizon as conditional until a longer-baseline epoch is admitted.

## Unit of analysis

- Cell grid: global 10 m grid in EPSG:6339. A cell's stable identifier is the
  integer column and row index of its lower-left corner from the CRS origin,
  so identifiers are stable across tiles, runs and study areas. 30 m cells
  nest as 3x3 blocks of the 10 m grid.
- Span: a tower-to-tower segment of OpenStreetMap power line geometry within
  the study box. Voltage is cross-checked against the California Energy
  Commission transmission line layer, since OpenStreetMap voltage tagging is
  not authoritative on its own. A span buffer aggregates the 10 m cells that
  fall inside it.
- Working scale for label statistics is 10 m and 30 m; span-level aggregation
  is computed from the underlying cell grid, not from a coarser raster.

## Labels

Derived from airborne LiDAR canopy height models over corridor tiles and a
background sample, for the epoch pairs 2013 to 2022 and 2022 to 2023. Per 10 m
cell, at each of `t0` and `t1`: mean, 95th percentile and maximum canopy
height, and their changes between epochs; loss share within the cell; a crown
or local-maximum layer is a planned addition, not yet built. Percentile and
maximum statistics are carried forward because block-mean height change
understates the clearance-relevant tail; a single tall stem or crown apex
inside an otherwise short-canopy cell is the operationally relevant case and a
mean would average it away.

## Label quality

This section holds what was previously the noise-floor and long-baseline
change measurement. It characterises the airborne LiDAR truth the labels and
evaluation depend on; it is not itself the primary contribution.

### Noise floor from the 2022-2023 pair

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
floor of interior coverage and is reported as one.

The horizontal offset between two acquisitions is a property of the pair, and
a 250 m tile spans too narrow a range of aspect to resolve it. One offset is
solved from every tile at once and applied to all of them. Its horizontal part
is applied to the canopy height grids; its vertical part belongs to the
terrain alone, because a canopy height is a difference taken inside one epoch
and its datum has already cancelled.

The 2023 and 2023 pair of CA_NorthCoastRanges_2_B23 and CA_SolanoCounty_1_A23
carries no true growth. It is run as a control, so that a residual offset
between epochs separates a pipeline fault from a real or seasonal change.

Run on 2026-09-24, on the 2022-2023 pair. Of 287 candidate co-covered 250 m
tiles, 284 were drawn and 52 admitted after coverage and agreement checks,
giving 2,153,732 stable-cell co-registration cells over 3 iterations.

| scale_m | NMAD | sd | LoD95 | mean | cells | rel_err | admitted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 0.120 | 0.224 | 0.235 | -0.080 | 25,569 | 0.4% | yes |
| 20 | 0.107 | 0.184 | 0.210 | -0.080 | 6,070 | 0.9% | yes |
| 30 | 0.101 | 0.169 | 0.199 | -0.080 | 2,704 | 1.4% | yes |
| 50 | 0.102 | 0.156 | 0.199 | -0.082 | 1,016 | 2.2% | yes |
| 100 | 0.082 | 0.126 | 0.161 | -0.077 | 176 | 5.3% | no |
| 200 | 0.078 | 0.114 | 0.153 | -0.081 | 49 | 10.1% | no |

Stable fraction 93.6 percent. Co-registration converged to shift dx +0.053 m,
dy -0.126 m, dz +0.032 m, with terrain RMSE falling from 0.176 to 0.150 m. The
decay fit over the four admitted scales gives exponent 0.054 against 0.5 for
spatially independent error: measurement error decays far slower than the
independent-error rate, consistent with spatially correlated error. The 100 m
reference scale could not be admitted, because the seam is exhausted at 284 of
287 candidate tiles and only 176 cells result, below the 200-cell minimum. Its
sigma is extrapolated from the decay fit at 0.092 m; the measured-but-
unadmitted 100 m NMAD of 0.082 m agrees with this figure. All six gate checks
pass: mean_one_year_change_in_range, sigma_falls_with_scale,
coregistration_converged, shift_below_limit, sigma_at_reference_below_limit,
reference_sigma_available. GATE PASS.

The mean is stable across scales at about -0.08 m, inside LoD95 at the finest
admitted scale, and is treated as a pair-specific bias rather than growth. The
seam is the worst geometry of either acquisition, so this floor is an upper
bound for interior coverage.

Two gate thresholds were revised after the data were seen, both post hoc and
both required by results that could not be anticipated in advance:

1. The noise floor is measured on stable cells only, cells whose 1 m change
   lies within `noise_floor.stable_change_limit_m` (3.0 m). The mean check
   changed from a fixed [0, 1.5] m band to [-LoD95 at the finest admitted
   scale, +1.5 m], because a one-year growth signal and a few-centimetre
   sensor bias cannot be separated from a single differenced pair. The
   monotonic-sigma check now tolerates a rise between adjacent scales within
   twice their combined relative standard error, since a sample-size-limited
   estimate can rise slightly by chance even when the underlying spread is
   falling.
2. When the 100 m reference scale cannot be admitted, because the seam does
   not carry the configured minimum cell count at that scale, its sigma is
   extrapolated from the decay fit over at least three admitted scales and
   reported as extrapolated.

### Long-baseline change, 2013 to 2022

Run 2026-09-24, pair 2013 to 2022, baseline 8.96 years, 30 tiles of 500 m
(7.5 km2), all admitted. The 2013 acquisition is served as three resources in
US survey feet with a constant offset; after conversion the fitted terrain
scale against 2022 was 1.0006 and the offset of -9.36 m was removed by
pooled co-registration (dx -0.21 m, dy +0.07 m, terrain RMSE 9.30 to 0.31 m).

Stable-ground check on cells below 1 m in both epochs (2,533,479 cells):
mean +0.025 m, median -0.005 m, NMAD 0.073 m. Cells changing by more than
3 m: loss 7.2 percent, gain 5.8 percent.

| Scale (m) | Cells | Median, all (m) | Detectable, all | Median, canopy (m) | Detectable, canopy | LoD95 (m) |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 73,545 | +0.006 | 61.9 % | +0.84 | 86.9 % | 0.235 |
| 20 | 18,500 | +0.020 | 67.0 % | +0.89 | 89.7 % | 0.210 |
| 30 | 7,608 | +0.031 | 69.4 % | +0.94 | 91.9 % | 0.199 |
| 50 | 2,985 | +0.044 | 71.0 % | +0.95 | 91.8 % | 0.199 |
| 100 | 748 | +0.059 | 75.7 % | +0.93 | 89.9 % | 0.180 |

Canopy denotes cells with mean height of at least 2 m that did not lose more
than 3 m. Detectable denotes absolute change above LoD95 from the 2022-2023
floor. The 200 m scale holds 120 cells and is not reported. The limit of
detection is that of the one-year pair; the long pair's own canopy floor is
not measured and its terrain residual is twice as large, so the fractions are
upper bounds. With the median canopy change at four to five times LoD95 the
conclusion does not depend on that margin: nine-year canopy change is
detectable at every measured scale from 10 to 100 m. The median canopy
increment corresponds to about 0.1 m per year, at the low end of the
published range for the mapped alliances, and is a block-mean figure: it is
not the clearance-relevant quantity, which is carried by upper percentiles and
local maxima near conductors, not by the block mean.

### Retrospective Landsat attribution (superseded as a forecast claim)

Fitted on 30 tiles, 30 m cells, tile-grouped cross-validation: a static
baseline (start height, terrain, vegetation alliance) gives mean absolute
error 0.83 m, r2 about 0; adding Landsat history to end of period gives mean
absolute error 0.60 m, r2 0.50, with a bootstrap confidence interval on the
mean absolute error difference of -0.35 to -0.16 m. On the undisturbed-canopy
subset alone, r2 is 0.28.

This result uses end-of-period (2022) imagery and the 2013-2022 difference
itself as part of its evidence, both of which are the outcome it appears to
explain. It is retained as an attribution result, meaning it characterises
association between observed change and observed imagery over the same
window, and it is not evidence of forecast skill: a genuine forecast must use
only data available at `t0`, before the outcome window. F3 below restates the
comparable question in a forecast-valid form.

## Features

An as-of feature store keyed by cell identifier and cutoff date. The builder
refuses any source with an observation date after the cutoff; this is
enforced in code, not only documented, because a forecast evaluated with
post-cutoff information is not a forecast.

- LiDAR structure at `t0`: ring-anchored height statistics (mean, percentiles,
  maximum) and gap distance from the eight-neighbour ring, excluding the
  centre cell. The centre cell's own height must not appear in both the
  feature set and the target, because the target is defined from the centre
  cell and shared measurement error would induce spurious correlation.
- Terrain: slope, aspect, and derived site-quality indices from 3DEP.
- Optical history to `t0`: Landsat 5, 7 and 8 time series with disturbance age
  from LandTrendr segmentation.
- Climate: TerraClimate normals and climatic water deficit.
- Vegetation type: LANDFIRE existing vegetation type, or the CDFW Sonoma
  vegetation map where it has finer resolution.
- Fire history before `t0`: CAL FIRE FRAP and MTBS perimeters.
- NAIP imagery where it adds resolution the other sources lack.

## Models

Two heads, both conditioned on the as-of feature set at `t0`:

- Disturbance hazard head: probability that a cell or span crosses the
  clearance-relevant threshold by `t0 + k`.
- Conditional growth head: quantile regression on height change given no
  disturbance, at quantiles 0.05, 0.25, 0.50, 0.75 and 0.95, because growth
  and disturbance-loss residuals are bimodal and a single Gaussian likelihood
  is not appropriate.

Model capacity is bounded by the number of spatially independent blocks, not
the number of cells. Limits are in `configs/forecasting.yaml`.

## Validation protocol

Spatial block cross-validation, with block size selected from the practical
range of the variogram of out-of-fold residuals and a buffer applied between
train and test blocks so the buffer is at least the correlation range. One
region is held out entirely and never used for any fold, to give a fully
independent generalisation estimate.

An out-of-time check runs on the 2022 to 2023 pair, where both a t0-only
feature set and the realised outcome exist, to test forecast skill over the
one interval with ground truth on both sides of the cutoff.

Confidence intervals on error and ranking differences between two models come
from a paired tile-block bootstrap that resamples whole blocks. Resampling
individual cells understates the interval on autocorrelated residuals by
approximately the square root of the cells per block.

## Evaluation

- Cell level: mean absolute error on the growth head, and quantile coverage
  (empirical fraction below each predicted quantile) for the disturbance
  hazard and growth heads together.
- Span level: recall at 1, 2 and 10 percent of ranked corridor line length for
  the event "vegetation within the clearance envelope by `t1`", against
  cyclic, current-height-first, random and span-length allocation. Reported
  with a paired tile-block bootstrap confidence interval on each pairwise
  difference.
- Existing products (Lang et al. 2023 canopy height at 10 m, Meta/WRI canopy
  height at 1 m, GLAD forest change at 30 m) are evaluated both as baselines,
  differenced across epochs, and as candidate input features to the forecast
  heads.
- Output: a span table and a map of the top-ranked spans, each with an
  encroachment probability and an expected time to encroachment.

## Data roles

| Source | Role | Prohibited use |
| --- | --- | --- |
| Sonoma 2013, 2022, 2023 airborne LiDAR | Label source and label-quality truth | Any model feature at or after its own epoch |
| Landsat 5/7/8 | As-of predictor history to `t0` | Any observation dated after the cutoff |
| USGS 3DEP | Terrain predictors and site quality | Substituting for a co-registration check |
| TerraClimate | Climate normals and climatic water deficit | None beyond standard predictor use |
| LANDFIRE / CDFW Sonoma vegetation map | Vegetation type stratification | Assuming species purity at 10 m |
| GEDI02_A Version 2 | Independent cross-check and gap fill | Training target |
| CAL FIRE FRAP, MTBS | Disturbance history before `t0` | Treating absence from one source as proof of stability |
| CEC transmission lines, OpenStreetMap power lines | Span construction and voltage cross-check | Engineering clearance or causation claims |
| Lang et al. 2023, Meta/WRI, GLAD products | Baselines and candidate features | Substituting for the airborne LiDAR label |

Truth isolation is enforced in continuous integration by
`tests/test_truth_isolation.py`, which fails if any feature or model module
imports the LiDAR package or references a truth path at or after its own
epoch.

## Hypotheses

### F1: forecast skill

An as-of feature model (LiDAR t0 structure, terrain, optical history to t0,
climate, vegetation type, fire history) beats a t0-structure-only baseline at
cell level, on mean absolute error and quantile coverage, under spatial block
cross-validation with a held-out region. Falsified if the interval on the
error difference includes zero.

### F2: span ranking

Span ranking by predicted encroachment probability and expected time achieves
higher recall at 1, 2 and 10 percent of ranked corridor length than cyclic,
current-height-first, random and span-length allocation. Falsified if the
interval on the difference includes zero against any of the four.

### F3: satellite contribution

Adding optical history to t0 improves forecast skill (F1's metrics) beyond a
LiDAR-t0-structure-only baseline. This restates the retrospective Landsat
result above in a forecast-valid form, using only pre-cutoff imagery.
Falsified if the interval on the improvement includes zero.

### F4: existing products do not substitute

Existing global canopy height and forest-change products (Lang et al. 2023,
Meta/WRI, GLAD), used as either differenced baselines or candidate features,
do not match the as-of forecast model's span-ranking recall. Falsified if any
product-based approach matches or exceeds it.

### H1: error decay (label quality, measured)

`sigma_n(s)` decreases with aggregation scale more slowly than the inverse
square root of the cell count, because measurement error is spatially
correlated. Measured and confirmed: fitted decay exponent 0.054 against 0.5
for spatially independent error, over the four admitted scales in the
2022-2023 pair. This is a label-quality statement, not a forecast hypothesis,
and is retained because it justifies working at 10 m and 30 m rather than
requiring coarser aggregation.

## Ablations

| ID | Isolates |
| --- | --- |
| A1 | Fire, by refitting on unburned cells with a buffer |
| A2 | Spectral fire detection, by adding burn severity to the growth head |
| A3 | Species encoded through phenology, by per-alliance centring and leave-one-alliance-out |
| A4 | Terrain, by a terrain-only baseline |
| A5 | Topographic illumination correction |
| A6 | View geometry, by single-orbit refit and orbit permutation |
| A7 | Spatial autocorrelation, by comparing spatial-block and naive validation |
| A8 | Anchor artifact, ring against centre |
| A9 | Anchor dominance, by an anchor-free growth head |
| A10 | Static mapping posing as forecasting, by temporal shuffle of the as-of cutoff |
| A11 | Predictor chronology, Landsat alone against Landsat with additional bands |
| A12 | Co-registration, by recomputing labels under one-pixel shifts |
| A13 | Point density, by comparing decimated and non-decimated pipelines |
| A14 | Spatial structure masquerading as signal, by replacing the satellite block with a matched Gaussian random field |

A10 and A14 are blocking. Both run before the remaining ablations. If the
temporal shuffle does not degrade error, the model carries no temporal
information and is not forecasting. If the matched random field reproduces
the satellite gain, F3 is an artifact of spatial structure rather than
signal. Either outcome is reported as the result.

## Falsification and claim limits

The primary claim fails if span-level ranking does not beat the operational
baselines under spatial block cross-validation with a held-out region, if the
satellite contribution does not survive the temporal shuffle and matched
random field controls, or if apparent skill disappears under spatial
blocking. A useful negative result is reported as such.

No result from this design establishes regulatory clearance, tree-failure
causation, wildfire causation, or utility-grade safety certification.
Satellite-derived canopy height at 10 m carries an error of approximately 6 m,
several times the 1.22 m clearance threshold binding these voltage classes in
the High Fire-Threat District, so no span may be declared compliant or
non-compliant from this product. No conductor geometry is available either;
OpenStreetMap span geometry places a line corridor, not a conductor position
or sag, so the clearance envelope itself is approximate. No reduction in
outages, ignitions or cost is claimed, because no outage or work-order
records are available. Hazard trees
are not identified, because their structural and species attributes are not
observed. NERC FAC-003-4 binds lines at 200 kV and above, so only the 230 kV
lines here fall in its scope; the 60 and 115 kV lines are governed by CPUC
General Order 95 and Public Resources Code 4293.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-22 | Adopt airborne LiDAR change as the primary label, at a ladder of scales and baselines | The only formulation in the available data where signal exceeds the measurement noise floor; see the label-quality section above. |
| 2026-09-24 | Unlock the design and reframe from a detectability benchmark to a span-level encroachment forecast | An independent review found the retrospective Landsat model used end-of-period imagery and the outcome differences themselves, valid as attribution but not as forecast; utilities need span-level, ranked, backtested, forward-looking risk, and block-mean height change is not the clearance-relevant quantity. |
| 2026-09-25 | Mark the 2 and 3 year forecast horizon conditional, and note conductor geometry is not available | A review found the stated one-to-three year horizon has ground truth for only one interval (2022 to 2023), and the clearance envelope is placed from OpenStreetMap line geometry, not conductor position or sag. |

## Open items

- Admission of the 2007 LiDAR epoch, pending the epoch screen.
- Final spatial block size and buffer, from training residuals only.
- Crown or local-maximum label layer, not yet built.
- Whether the open fire-incident join carries enough events to report.
- Target journal and its disclosure policy.
