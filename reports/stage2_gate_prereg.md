# Stage-two residual gate: preregistration

Status: frozen before any E4 or E5 fit. Date: 2026-10-15. This record must be committed before fitting. The G3 results in `reports/growth_curve_check_2013-2022.md` are prior evidence, not stage-two results.

## Target and comparison

The cell target is observed 2013-to-2022 airborne-LiDAR p95 height change minus the stage-one type-specific (or pooled broad-group) median increment for the cell's 2013 Sonoma map class. The median is fitted only in each spatial training fold. The baseline is the stage-one median prior alone, evaluated out of fold on exactly the same cells as each stage-two model. The stage-two prediction adds a predicted residual to that training-fold median increment. Neither a full-sample stage-one fit nor held-out target values may enter a held-out prediction.

## Population and temporal boundary

The primary population is the forest LiDAR-loss-OFF screen already defined by `canopyguard.evaluation.growth_screen.selection_masks`, including the existing wire, fire and Hansen exclusions. The forest LiDAR-loss-ON screen is reported as a retrospectively selected undisturbed-canopy upper bound; it is not the headline. Both screens rely on some retrospective screening and are not fully prospective 2013 forecast evaluations. All-class comparisons use the same screen logic as a declared sensitivity. Cells without a valid static DEM value are excluded before fitting, and the excluded count and the stage-one baseline on the identical retained cells must be reported.

Predictors are frozen to 2013 LiDAR `mean_start`, `p95_start`, and `max_start`; 2013 Sonoma `vegetation_type`; and four static terrain fields: `elevation_m`, `slope_deg`, `heat_load`, and `tpi_450`. The terrain fields come from a documented public DEM and are joined 1:1 by `cell_id` on the measured 10 m LiDAR label grid in EPSG:6339. Only training-fold data may set numeric imputation medians, standardization parameters, or vegetation encoding. Unknown vegetation categories in a held-out fold receive zero encoded indicators. Target-epoch LiDAR, `lidar_loss`, post-2013 disturbance flags, Sentinel-2, GEDI, and ECHOSAT are never predictors. The last three sources have no role in the 2013 forecast fit.

## Evaluation and fixed models

Use five spatial folds with 2 km square blocks, seed 42, via `canopyguard.evaluation.blocks.assign_blocks` and `systematic_folds`. Compare paired cell absolute errors with 2,000 whole-block bootstrap draws, seed 42, via `canopyguard.forecasting.growth_curve.block_mae_interval`. The interval holds fold fits fixed and omits refit variance. The point metric is cell-weighted MAE in metres. Report fold counts, cell counts, and block counts.

E4 is scikit-learn ridge with alpha 1.0. Numeric predictors are training-median imputed then standardized; vegetation class is one-hot encoded. E5 is LightGBM regression with max depth 4, 15 leaves, 400 estimators, learning rate 0.03, minimum 200 cells per leaf, feature fraction 0.6, and seed 42. Its categorical map class is encoded using the same training-only vocabulary. These settings are recorded in `configs/forecasting.yaml`, remain under its capacity ceiling, and are used for one fit per fold per declared screen and block-size evaluation. No other model family, hyperparameter search, feature search, or screen selection is permitted after seeing results.

For reproducible execution, LightGBM uses deterministic and column-wise modes with four threads. These execution controls are frozen before the first E4 or E5 fit.

## Decision and declared sensitivities

For each model separately, PASS requires the 95% whole-block interval for (model MAE minus stage-one prior MAE) to lie entirely below zero on the forest LiDAR-loss-OFF 2 km screen. An interval touching or crossing zero is FAIL. The forest LiDAR-loss-ON comparison is reported as a retrospective upper bound. Declared sensitivities are 1 km and 5 km blocks, and forest-only versus all admissible map classes, using the same fixed settings and showing the matched stage-one baseline. A null or negative result is a reportable finding. It is not grounds to change the gate, settings, blocks, features, or screens.

Scientific interpretation remains subject to human review tracked in issue #19. This preregistration does not record scientific sign-off or change `growth_curve.human_review`.
