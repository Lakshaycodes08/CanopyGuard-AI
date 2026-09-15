# CanopyGuard-AI from scratch

Updated: 2026-09-15

Audience: a teammate who is new to machine learning, remote sensing, and the
current repository.

## 1. The project in one sentence

CanopyGuard-AI tests whether open satellite observations can help forecast
future tree-canopy height near approximate power-line corridors, and whether
that forecast can improve research-grade maintenance prioritization.

This is a scientific study, not a utility safety system. Its outputs cannot
certify clearance, predict a particular tree failure, or replace an engineering
survey.

## 2. The central idea

Imagine trying to monitor a large forest every month:

- Sentinel-2 is the frequent camera. It sees the whole area repeatedly but does
  not directly measure tree height.
- GEDI is a sparse laser ruler from space. It gives height-like measurements at
  scattered footprints, not a complete map.
- Airborne LiDAR is the detailed reference survey. We have Sonoma canopy
  products for 2013 and 2022, so the 2022 product is kept independent for the
  final check.
- The vegetation map provides broad ecological context.
- Fire records and Landsat change evidence help separate slow growth from
  abrupt canopy loss.
- California Energy Commission transmission lines provide approximate corridor
  context. They are not survey-grade conductor geometry.

The intended evidence chain is:

```text
raw source catalogues
        |
        v
downloaded and clipped source files
        |
        v
aligned monthly Sentinel-2 cube + filtered GEDI targets
        |
        v
simple baselines -> candidate ML models -> locked 2022 evaluation
                                            |
                                            v
                              independent LiDAR comparison
                                            |
                                            v
                          risk ranking -> schedule comparison
                                            |
                                            v
                              figures, claims, and paper
```

Every arrow must produce a documented file so a teammate can rerun one stage
without repeating everything manually.

## 3. What question are we testing?

The locked primary question is:

Can a locally calibrated model using the previous calendar year of monthly
Sentinel-2 observations and sparse GEDI height references predict canopy height
one year ahead more accurately than simple non-temporal baselines, under
chronological and spatially blocked evaluation, and are the predictions useful
for ranking vegetation priority when checked against independent 2022 LiDAR?

The exact hypotheses and failure conditions are in
`reports/research_design.md`.

## 4. What is a machine-learning problem?

Machine learning means learning a numerical relationship from examples rather
than writing every rule manually.

Each training example has:

- Features: information given to the model. Here these may include monthly
  Sentinel-2 band values, vegetation indices, observation counts, terrain, and
  carefully justified ecological context.
- Target or label: the value the model tries to predict. The planned target is
  GEDI RH98 canopy height in meters.
- Model: the learned mathematical mapping from features to the target.
- Prediction: the model's estimated height for a new place and time.

Our main task is regression because canopy height is a continuous number such
as 8.4 m. Classification would instead predict categories such as low, medium,
or high.

## 5. Important remote-sensing and map concepts

### Raster and pixel

A raster is a grid. A Sentinel-2 10 m pixel represents an approximately 10 m by
10 m ground cell. It does not represent one individual tree.

### Band

A band measures reflected light in one wavelength range. Different bands are
sensitive to visible color, vegetation structure, water, and moisture. A model
uses several bands together rather than treating the satellite image as a
normal photograph.

### CRS

A coordinate reference system explains how map coordinates relate to Earth.
The study area is recorded in latitude and longitude as EPSG:4326. Analysis is
planned in UTM zone 10N, EPSG:32610, where distances are measured in meters.

### Reprojection and resampling

Reprojection transforms data into a common CRS. Resampling determines pixel
values on the new grid. Continuous reflectance can use bilinear resampling;
categorical layers such as cloud classes must use nearest-neighbor resampling.

### Alignment

Two rasters are aligned only when they have the same CRS, pixel size, bounds,
and pixel origin. Similar-looking maps can still be misaligned and produce bad
training pairs.

### Cloud masking and no-data

Clouds, shadows, cirrus, snow, defective pixels, and missing pixels must not be
treated as land observations. Sentinel-2 digital number 0 is no-data. The code
masks configured Scene Classification Layer classes and counts how many clear
observations contributed to each monthly pixel.

### Composite

Several clear observations in one month are combined into one value. The
current design uses the median because it is less sensitive to remaining
outliers than the mean.

### Data cube

The cube is an organized array with dimensions `time`, `band`, `y`, and `x`.
It is the model-ready history of the study area, not a mysterious database.

## 6. The five main data roles

| Source | What it contributes | What it must not be treated as |
| --- | --- | --- |
| Sentinel-2 Level-2A | Dense monthly optical history | Direct tree-height truth |
| GEDI02_A Version 2 | Sparse RH98 height reference | A wall-to-wall map |
| Sonoma 2013 and 2022 LiDAR products | Persistence comparison and independent validation | Ordinary model features |
| CEC transmission lines | Approximate corridor aggregation | Exact conductor or clearance geometry |
| Vegetation and disturbance evidence | Stratification, weak priors, and change screening | Proof of one cause or one species per pixel |

Keeping these roles separate prevents circular evaluation. For example, if the
2022 LiDAR truth is used to train the model, it can no longer be an independent
2022 test.

## 7. The study setup

- Study area: northern Sonoma County candidate, now confirmed.
- Bounding box: west -122.90, south 38.475, east -122.74, north 38.82.
- First Sentinel tile: MGRS 10SEH.
- Study dates: 2017-01-01 through 2022-12-31.
- Training period ends: 2020-12-31.
- Validation period: calendar year 2021.
- Test period: calendar year 2022.
- Working grid: 10 m in EPSG:32610.

The code rejects overlapping or out-of-order time splits.

## 8. Why three time periods?

- Training data teach the model.
- Validation data help choose settings and compare candidate models.
- Test data answer the final question after all choices are frozen.

Looking repeatedly at test results and changing the model is similar to seeing
an exam answer key while studying. It creates test leakage and makes reported
performance look better than real future performance.

Nearby forest pixels are also similar. Therefore the evaluation uses spatial
blocks so neighboring pixels do not casually leak information across a split.
Candidate block sizes are 1, 2, and 5 km, selected using training evidence only.

## 9. Models we plan to use

### Baselines first

A baseline is a simple method that a more complex model must beat.

1. Training median: always predict the median training height.
2. Vegetation-class median: predict a separate training median for each broad
   vegetation class.
3. Snapshot Random Forest: use one contemporary snapshot without monthly
   history.
4. 2013 LiDAR persistence: assume the earlier LiDAR height persists, only for
   the independent LiDAR comparison where alignment permits it.

If a complex model cannot beat these, complexity has not added scientific
value.

### Candidate models

- Random Forest: many decision trees learn different rules and average their
  predictions. It handles nonlinear relationships and mixed features well.
- Histogram Gradient Boosting: trees are added sequentially to correct earlier
  errors. It is efficient and often strong for tabular data.

Both can run on CPUs. A neural network and GPU are not part of the minimum
experiment. They are justified only if the baselines reveal a specific problem
that simpler models cannot solve.

## 10. Terms needed to understand model results

- Overfitting: memorizing training patterns that do not generalize.
- Leakage: information from the future or test set reaches training or model
  selection.
- Hyperparameter: a setting chosen before fitting, such as tree depth.
- Feature engineering: turning raw data into meaningful inputs.
- Inference: using a fitted model to make predictions.
- Ablation: remove one component and measure whether performance changes.
- Uncertainty: how unsure a prediction or reported difference is.
- Reproducibility: another teammate can regenerate the result from recorded
  code, configuration, data versions, and seeds.

## 11. Evaluation metrics

- MAE: average absolute error in meters. This is the primary metric because it
  is easy to interpret.
- RMSE: similar to MAE but penalizes large errors more strongly.
- Bias: average signed error. Positive bias means overprediction; negative bias
  means underprediction.
- R2: how much target variation is explained relative to predicting a constant.
  It can be negative on difficult test data.

Metrics will also be reported by height class, vegetation class, and
disturbance status. One overall number can hide failure on tall trees or burned
areas.

A paired spatial-block bootstrap will estimate a 95 percent interval for model
differences. The main forecast claim is supported only if the temporal model's
MAE improvement over the best simple baseline remains below zero across that
interval.

## 12. What is already completed and verified?

### Scientific feasibility

Phase 0 is GO. The exact study box has approximate line context, overlapping
2013 and 2022 LiDAR products, quality-filtered GEDI coverage, sufficient
Sentinel-2 catalogue coverage, comparison forest, and independent disturbance
evidence. Exact counts and limitations are in `reports/data_feasibility.md`.

### Research design

The primary question, hypotheses, source roles, baselines, ablations, metrics,
time split, spatial validation, and falsification rules are predeclared in
`reports/research_design.md`.

### Literature check

The current core literature matrix shows that growth-aware monitoring, risk
modeling, and scheduling already exist. We cannot claim the first integrated
system. The provisional contribution is the open, leakage-resistant evidence
chain with independent repeat-LiDAR validation. A systematic review is still
required before an absolute novelty statement.

### Repository foundation

- YAML files hold study, ingestion, forecasting, risk, and scheduling settings.
- The Sentinel-2 catalogue stage retained 458 Level-2A acquisitions with all 11
  configured assets.
- DVC records the current Sentinel manifest stage.
- Offline cube functions implement metadata-based reflectance scaling, no-data
  masking, monthly clear-pixel medians, clear counts, and storage estimation.
- Seed and time-split utilities exist.
- Thirty-five offline tests pass. Ruff and text-hygiene checks pass.

## 13. What has not happened yet?

- The 458 raster acquisitions have not been downloaded and clipped.
- The real monthly Sentinel-2 cube has not been built.
- Pixel-level clear-observation availability has not been measured.
- GEDI targets have not been turned into the final aligned training table.
- The two LiDAR epochs have not completed alignment and quality control.
- No model has been trained.
- No performance metric, risk map, schedule result, or paper result exists.
- No DVC remote or NSUT job script exists because storage and scheduler details
  are not yet known.

Code being present is not proof that the scientific result works.

## 14. What happens after NSUT access?

### Stage A: infrastructure setup

Clone the repository, create the Conda environment, run offline checks,
configure shared persistent and scratch paths, and create one shared DVC remote.

Exit check: a teammate can clone the same commit, run tests, and access the DVC
remote without credentials entering Git.

### Stage B: Sentinel-2 raster ingestion

Read only the study-area windows from each configured asset where possible,
verify metadata scaling, reproject to the locked 10 m grid, mask invalid pixels,
and write documented interim files.

Exit check: scene counts match the manifest, grid metadata match the config,
and rendered samples show no shifts or corrupted masks.

### Stage C: monthly cube

Build monthly median composites and clear-observation counts in Zarr format.

Exit check: every month and band has expected dimensions, missingness is
reported, and the minimum-clear-observation rule is chosen from training data.

### Stage D: GEDI and LiDAR preparation

Filter GEDI quality flags, align footprints with predictor dates and pixels,
then independently align and inspect 2013 and 2022 LiDAR surfaces.

Exit check: spatial offsets, missing areas, footprint counts, height ranges, and
disturbance strata are documented.

### Stage E: model-ready table

Join each eligible GEDI target only to preceding predictor information. Assign
time and spatial-block identifiers before model fitting.

Exit check: automated tests show no future feature, duplicate target, test
leakage, or train-test spatial overlap under the selected blocks.

### Stage F: baseline and candidate experiments

Fit baselines first, tune Random Forest and histogram boosting on training plus
2021 validation rules, freeze the selected pipeline, then evaluate 2022 once.

Exit check: logged parameters, seed, metrics, data hashes, Git commit, error
strata, bootstrap intervals, and LiDAR comparison are complete.

### Stage G: risk and scheduling study

Convert forecast evidence and uncertainty into research-priority scenarios near
approximate corridors. Compare forecast-based scheduling with random,
current-height, static-risk, and simple highest-risk-first rules under identical
budgets.

Exit check: sensitivity analysis is reported and outputs clearly state they are
not regulatory or engineering decisions.

### Stage H: paper and release

Create final figures and tables, finish the systematic review, reconcile every
claim with `reports/claims_log.md`, rerun the full pipeline, archive the exact
Git and DVC versions, and disclose AI use according to the selected venue.

## 15. Why NSUT resources help

The estimated uncompressed clipped source array is about 90.43 GiB. The monthly
cube is about 15 GiB, while reprojection, caches, intermediate data, and reruns
need additional room. The current request is at least 300 GiB persistent
storage plus 300 GiB scratch.

- Persistent storage keeps authoritative inputs and verified outputs.
- Scratch storage is fast temporary space for jobs.
- CPU and RAM matter first for download, reprojection, cube construction, and
  tree models.
- A GPU may help only if a later deep-learning experiment is justified.
- A scheduler such as Slurm or PBS decides when and where cluster jobs run.

Details to request from NSUT are in `reports/hpc_readiness.md`.

## 16. How Git, DVC, and configuration fit together

- Git versions small files: code, tests, configurations, and reports.
- DVC versions large data and model artifacts without placing them inside Git.
- `environment.yml` defines the reproducible software environment.
- `configs/*.yaml` define the experiment without hiding settings inside code.
- `dvc.yaml` defines the data-stage dependency graph.
- Tests catch logic and contract errors using tiny offline examples.
- Seeds reduce accidental randomness between runs.
- The claims log connects scientific statements to sources.

No raw raster, point cloud, Parquet file, credential, or token belongs in Git.

## 17. Suggested team ownership

- Data owner: ingestion, source provenance, DVC, and storage.
- Cube-quality owner: projection, alignment, cloud masks, and visual samples.
- Modeling owner: baselines, features, splits, experiments, and logs.
- Validation owner: LiDAR, disturbance subsets, metrics, and error analysis.
- Scheduling owner: constraints, baselines, sensitivity, and claim limits.
- Paper owner: literature, claims log, figures, venue rules, and release.

Every important output should be checked by a teammate who did not create it.

## 18. What you should learn first

Do not try to learn all of remote sensing and ML at once. Learn in this order:

1. Read Sections 1 through 8 of this guide and explain the five data roles in
   your own words.
2. Learn raster, band, CRS, pixel, masking, alignment, and data cube.
3. Learn feature, target, regression, training, validation, test, leakage, and
   baseline.
4. Understand MAE, RMSE, bias, and why a spatial block is required.
5. Follow one tiny dataset through a notebook or script only after the real cube
   pipeline exists.
6. Learn DVC and the NSUT scheduler when access is granted.

You do not need to derive every ML algorithm mathematically before helping.
You do need to understand what information enters the model, what truth it is
compared with, and why the test data remain untouched.

## 19. Common mistakes to prevent

- Training on 2022 LiDAR and then calling it independent validation.
- Randomly shuffling pixels across time or neighboring train/test areas.
- Treating tile cloud percentage as pixel-level cloud masking.
- Mixing data with different grids without explicit alignment.
- Treating GEDI footprints as a complete height map.
- Claiming optical imagery measures small annual growth when errors are larger
  than that growth.
- Choosing thresholds after seeing test performance.
- Adding a neural network because a GPU is available.
- Reporting only the best model while hiding failed baselines or ablations.
- Committing raw data, secrets, or untraceable manual outputs.

## 20. Current decision and your immediate action

Decision: Phase 1 data foundation is active. Phase 0 feasibility is GO, but no
ML result is proven because the real aligned dataset does not exist yet.

Your immediate action is to send the access request in
`reports/hpc_readiness.md` and return with the scheduler, storage paths and
quotas, CPU and RAM limits, GPU information, Conda availability, outbound
network policy, and approved secret-storage method.

After that, the next technical action is shared storage and DVC setup followed
by the clipped Sentinel-2 cube. Model training comes only after cube, GEDI, and
LiDAR quality gates pass.

## 21. Source-of-truth documents

- `MEMORY.md`: current project handoff and immediate next action.
- `reports/data_feasibility.md`: exact Phase 0 evidence.
- `reports/research_design.md`: locked research question and experiment rules.
- `reports/literature_review.md`: current novelty evidence and limitations.
- `reports/phase1_data_protocol.md`: growth and disturbance protocol.
- `reports/hpc_readiness.md`: compute, storage, access, and team workflow.
- `reports/claims_log.md`: verified scientific and dataset claims.
- `configs/*.yaml`: machine-readable project and experiment settings.
- `AGENTS.md`: repository coding and scientific-integrity rules.
