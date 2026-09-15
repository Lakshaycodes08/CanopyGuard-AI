# CanopyGuard-AI research design

Locked before model training: 2026-09-15

## Decision

Status: PRE-DATA DESIGN LOCKED

This document fixes the primary question, hypotheses, data roles, baselines,
splits, metrics, and claim rules before the team sees test results. Data-quality
thresholds that require empirical calibration remain explicitly pending.

## Primary research question

Can a locally calibrated model using the preceding calendar year of monthly
Sentinel-2 observations and sparse GEDI reference heights predict canopy height
one year ahead more accurately than non-temporal baselines, under chronological
and spatially blocked evaluation, and are the predictions useful for ranking
vegetation priority near approximate transmission corridors when checked
against independent 2022 airborne LiDAR?

The intended contribution is an open and auditable evidence chain. It is not a
claim of first-ever vegetation detection, growth forecasting, risk assessment,
or maintenance optimization.

## Analysis unit and target

- Prediction grid: 10 m cells in EPSG:32610 inside the confirmed study area and
  Sentinel-2 tile 10SEH.
- Forecast target: GEDI02_A Version 2 RH98 in meters for the target year.
- Predictor window: the complete calendar year before the target year.
- Forecast horizon: 12 months.
- Independent validation: Sonoma 2022 canopy-height LiDAR after alignment and
  quality control.
- Independent persistence comparator: the aligned 2013 LiDAR surface.
- Corridor geometry: approximate context and aggregation only, never
  survey-grade clearance truth.

## Hypotheses

### H1: forecast skill

The selected temporal model will have lower 2022 spatial-block MAE than the
best simple non-temporal baseline. The claim is supported only when the paired
95 percent spatial-block bootstrap interval for the MAE difference is below
zero on the locked test set.

### H2: temporal value

The temporal model will have lower 2022 MAE than the same model family using a
single snapshot. This tests whether monthly history contributes information
beyond contemporary spectral structure.

### H3: ecological-prior value

On pixels where vegetation class and an independently defensible age proxy are
available, the ecological-prior variant will have lower MAE than the identical
no-prior variant. If no defensible age proxy exists, this hypothesis is reported
as not testable rather than replacing age-aware evidence with one universal
growth constant.

### H4: scheduling value

Under the same synthetic budget and work constraints, forecast-ranked schedules
will capture more held-out future priority than random, current-height, static
risk, and highest-current-risk baselines. This is a secondary decision-analysis
hypothesis because the corridor geometry and costs are approximate.

## Data roles

| Source | Role | Prohibited use |
| --- | --- | --- |
| Sentinel-2 Level-2A | Monthly temporal predictors | Tile cloud percentage as a substitute for pixel masking |
| GEDI02_A Version 2 | Sparse training and evaluation target | Unfiltered footprints or random pixel leakage |
| Sonoma 2013 LiDAR | Persistence comparator and alignment context | Ordinary model feature |
| Sonoma 2022 LiDAR | Independent validation truth | Training or model selection |
| Sonoma vegetation map | Stratification and eligible prior classes | Assuming every 10 m pixel is species-pure |
| CAL FIRE, MTBS, Landsat change | Disturbance status | Treating absence from one source as proof of stability |
| CEC transmission lines | Approximate corridor aggregation | Engineering clearance or causation claims |

## Locked split and model-selection protocol

1. Training targets end on 2020-12-31.
2. All tuning and model choice use 2021 only.
3. The 2022 test set is evaluated once after choices are frozen.
4. Spatial blocks, not random pixels, separate nearby observations.
5. Candidate block sizes are 1, 2, and 5 km. The primary size is the smallest
   candidate at or above the training-residual autocorrelation range. Test
   labels cannot influence the choice.
6. Candidate model families are Random Forest and histogram gradient boosting.
   A deep model is added only if these baselines expose a concrete limitation.

Blocked validation is required because random validation can underestimate
error when ecological data are spatially or temporally dependent. Source:
[Roberts et al. (2017)](https://doi.org/10.1111/ecog.02881).

## Baselines and ablations

Baselines:

1. Training-target median.
2. Training median by vegetation class.
3. Snapshot Random Forest without monthly history.
4. Aligned 2013 LiDAR persistence, used only for the LiDAR comparison.

Ablations:

1. Remove temporal history.
2. Remove the disturbance screen.
3. Remove the ecological prior on the eligible subset.

## Evaluation outputs

- Primary metric: MAE in meters.
- Secondary metrics: RMSE, signed bias, and R2.
- Strata: canopy-height class, vegetation class, and disturbance status.
- Uncertainty: paired spatial-block bootstrap intervals.
- Error analysis: maps and summaries for tall-canopy underestimation,
  disturbance errors, cloud availability, and spatial extrapolation.
- Every experiment records the config, seed, metrics, data hashes, and Git
  commit.

## Falsification and claim limits

The primary claim fails if the temporal model does not beat the best simple
baseline on the locked 2022 spatial test, if independent LiDAR error is too
large for stable ranking, or if the apparent improvement disappears under
spatial blocking. A useful negative result will be reported honestly.

No result from this design establishes regulatory clearance, tree-failure
causation, wildfire causation, or utility-grade safety certification.

## Pending decisions that require data or supervision

- Minimum clear-observation gate, calibrated from the actual cube.
- Final spatial block size, selected from training residuals only.
- Whether H3 has an adequate age proxy.
- Risk thresholds and scheduling costs, which remain scenario parameters until
  authoritative utility evidence is available.
- Target journal and its AI-disclosure policy.
