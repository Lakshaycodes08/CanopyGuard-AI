# Stage-two residual check, 2013-2022

Run: 2026-10-15T13:02:48.068794+00:00. Base revision: `c6b342fe96950c7e3986b131733d49438ccab387`.

The model-fitting and scoring implementation used in this run was committed unchanged after execution at `12296cf5712af4d1da009881f13396447d128f78`; the run base revision above contains the frozen preregistration. Its source and data hashes are recorded in `dvc.lock` and the output provenance sidecar. Report wording was clarified after the run without changing scores.

## Preregistered decision

Each E4 ridge and E5 LightGBM model passes only if the 95% whole-block interval for its MAE minus the matched training-fold stage-one median MAE lies entirely below zero on the forest LiDAR-loss-OFF 2 km screen. The LiDAR-loss-ON screen is a retrospectively selected upper bound. The loss-OFF screen also uses retrospective fire and Hansen screens; neither is a fully prospective 2013 evaluation. This rule, feature set, settings, and sensitivities were frozen in `reports/stage2_gate_prereg.md` before E4 or E5 fitting.

**E4 ridge: FAIL. E5 LightGBM: FAIL.**

## Paired spatial comparisons

Cell-weighted MAE and model-minus-stage-one differences are metres. Intervals use 2,000 whole-block draws with fold fits fixed; they omit refit variance. Each row refits the stage-one median and both models in five spatial training folds on the same retained cells.

| Screen | Block | Cells | Blocks | Stage 1 MAE | Ridge MAE | Ridge - stage 1 [95% CI] | Ridge CI below zero? | LightGBM MAE | LightGBM - stage 1 [95% CI] | LightGBM CI below zero? |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| forest loss off | 2000m | 125,888 | 83 | 1.256 | 1.336 | +0.080 [+0.060, +0.101] | FAIL | 1.309 | +0.052 [+0.029, +0.083] | FAIL |
| forest loss on | 2000m | 76,980 | 82 | 0.782 | 0.762 | -0.020 [-0.037, -0.001] | PASS | 0.751 | -0.031 [-0.054, -0.008] | PASS |
| all loss off | 2000m | 140,530 | 84 | 1.358 | 1.439 | +0.081 [+0.063, +0.100] | FAIL | 1.410 | +0.052 [+0.031, +0.075] | FAIL |
| all loss on | 2000m | 83,772 | 83 | 0.825 | 0.810 | -0.014 [-0.033, +0.003] | FAIL | 0.793 | -0.031 [-0.052, -0.012] | PASS |
| forest loss off | 1000m | 125,888 | 202 | 1.257 | 1.328 | +0.072 [+0.054, +0.088] | FAIL | 1.309 | +0.053 [+0.033, +0.073] | FAIL |
| forest loss on | 1000m | 76,980 | 198 | 0.778 | 0.761 | -0.017 [-0.034, -0.001] | PASS | 0.750 | -0.028 [-0.050, -0.008] | PASS |
| all loss off | 1000m | 140,530 | 211 | 1.359 | 1.435 | +0.076 [+0.059, +0.092] | FAIL | 1.408 | +0.048 [+0.031, +0.067] | FAIL |
| all loss on | 1000m | 83,772 | 207 | 0.822 | 0.801 | -0.021 [-0.036, -0.005] | PASS | 0.797 | -0.025 [-0.045, -0.007] | PASS |
| forest loss off | 5000m | 125,888 | 18 | 1.259 | 1.336 | +0.076 [+0.047, +0.116] | FAIL | 1.340 | +0.080 [+0.044, +0.130] | FAIL |
| forest loss on | 5000m | 76,980 | 18 | 0.784 | 0.791 | +0.007 [-0.037, +0.050] | FAIL | 0.797 | +0.013 [-0.052, +0.099] | FAIL |
| all loss off | 5000m | 140,530 | 18 | 1.362 | 1.445 | +0.083 [+0.054, +0.120] | FAIL | 1.441 | +0.079 [+0.044, +0.130] | FAIL |
| all loss on | 5000m | 83,772 | 18 | 0.827 | 0.825 | -0.001 [-0.037, +0.035] | FAIL | 0.829 | +0.002 [-0.053, +0.071] | FAIL |

## Inputs, omissions, and fit counts

The observed 2013-to-2022 p95 height change is the target. The only predictors are 2013 mean/p95/max LiDAR height, the 2013 Sonoma map class, and four static 3DEP terrain fields joined by existing 10 m cell IDs in EPSG:6339. The target residual subtracts the median increment fitted on each training fold. All preprocessing, including vegetation vocabulary and numeric imputation, is fit on training cells only. No 2022 LiDAR or later satellite observation is a predictor.

Terrain-null exclusions before model fit: all_loss_off 0, all_loss_on 0, forest_loss_off 0, forest_loss_on 0.

Software: scikit-learn 1.9.0; LightGBM 4.7.0. Five folds per row; each fold has one fixed-setting fit per model. No hyperparameter or feature tuning was performed.

Primary fold training/test cell counts: fold 0: 106,364/19,524; fold 1: 105,901/19,987; fold 2: 87,773/38,115; fold 3: 105,040/20,848; fold 4: 98,474/27,414.

## Primary-screen feature weights

Ridge coefficients are means across folds after training-fold standardization of numeric predictors; vegetation indicators are unscaled. LightGBM values are mean split gain, useful for ranking within this fitted model only. Zero is used when a category is absent from a fold's training vocabulary.

| Encoded feature | Mean ridge coefficient | Mean LightGBM gain |
| --- | ---: | ---: |
| numeric__elevation_m | -0.0503 | 417795.6 |
| numeric__heat_load | -0.1113 | 107878.5 |
| numeric__max_start | +1.9552 | 229175.4 |
| numeric__mean_start | +0.9381 | 205783.3 |
| numeric__p95_start | -3.2044 | 305869.8 |
| numeric__slope_deg | +0.0212 | 178270.6 |
| numeric__tpi_450 | -0.0170 | 195969.2 |
| vegetation__vegetation_type_Acer macrophyllum Alliance | +0.6650 | 1359.8 |
| vegetation__vegetation_type_Arbutus menziesii Alliance | -0.0861 | 18852.6 |
| vegetation__vegetation_type_Eucalyptus (globulus, camaldulensis) Semi-natural Alliance | -0.1376 | 10908.9 |
| vegetation__vegetation_type_Hesperocyparis sargentii Alliance | -0.2294 | 830.2 |
| vegetation__vegetation_type_Pinus attenuata Alliance | -0.2849 | 6311.9 |
| vegetation__vegetation_type_Pinus sabiniana / Quercus durata Provisional Alliance | -0.1914 | 3763.0 |
| vegetation__vegetation_type_Populus fremontii Alliance | -0.1218 | 8834.4 |
| vegetation__vegetation_type_Pseudotsuga menziesii Alliance | +0.3246 | 6168.1 |
| vegetation__vegetation_type_Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | -0.0968 | 29465.2 |
| vegetation__vegetation_type_Quercus agrifolia Alliance | -0.0052 | 14573.1 |
| vegetation__vegetation_type_Quercus chrysolepis Alliance | -0.1103 | 94.6 |
| vegetation__vegetation_type_Quercus douglasii Alliance | -0.1945 | 7760.2 |
| vegetation__vegetation_type_Quercus garryana Alliance | +0.0110 | 311.9 |
| vegetation__vegetation_type_Quercus kelloggii Alliance | +0.1061 | 13058.7 |
| vegetation__vegetation_type_Quercus lobata Alliance | -0.3452 | 46846.5 |
| vegetation__vegetation_type_Quercus wislizeni (tree) Alliance | -0.1084 | 3418.5 |
| vegetation__vegetation_type_Sequoia sempervirens Alliance | +0.7293 | 7115.3 |
| vegetation__vegetation_type_Umbellularia californica Alliance | +0.0754 | 5134.3 |

## Interpretation limit

The positive LiDAR-loss-ON sensitivity does not rescue either model's failing preregistered loss-OFF result. Its screen uses target-epoch LiDAR loss and is an optimistic upper bound.

A PASS applies to this screened, spatially blocked comparison and does not establish future-year forecast skill, causal terrain effects, species-pure growth, or engineering clearance. A FAIL is retained as the preregistered result. Scientific review of the G3 prior remains pending in issue #19.
