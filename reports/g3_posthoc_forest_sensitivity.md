# G3 post hoc forest and objective sensitivities

These analyses were designed after seeing the G3 and stage-two results.
They do not revise the frozen G3 or E4/E5 decisions.

## Forest population

All forest keeps label quality, 2013 canopy, map-class, line-distance,
and wire exclusions but does not remove cells for 2013-2022 fire,
Hansen loss, or LiDAR loss. The screened comparison retains the G3
fire/Hansen rules but does not apply the LiDAR-loss filter.
Each row refits the map-class or pooled-group median increment in
5 spatial training folds. Intervals use 2,000 whole-block bootstrap draws
with fitted predictions held fixed.

| Population and block | Cells | Blocks | No-change MAE | Median MAE | Median - no change [95% CI], m |
| --- | ---: | ---: | ---: | ---: | --- |
| all forest, 2000 m | 402,728 | 129 | 1.952 | 1.890 | -0.062 [-0.144, +0.012] |
| all forest, 1000 m | 402,728 | 363 | 1.952 | 1.891 | -0.061 [-0.122, -0.002] |
| all forest, 5000 m | 402,728 | 24 | 1.952 | 1.935 | -0.016 [-0.079, +0.052] |
| fire/Hansen screened forest, 2000 m | 125,888 | 83 | 1.378 | 1.256 | -0.121 [-0.145, -0.097] |
| fire/Hansen screened forest, 1000 m | 125,888 | 202 | 1.378 | 1.257 | -0.121 [-0.140, -0.103] |
| fire/Hansen screened forest, 5000 m | 125,888 | 18 | 1.378 | 1.259 | -0.118 [-0.143, -0.093] |

The screened loss-off comparison excludes 276,840 of the eligible all-forest cells based on later fire or Hansen loss.
The screened improvement does not establish the same
performance across all forest in this fire-dominated box.

## Squared-error objective diagnostic

On the screened forest at 2 km, an intercept-only residual model adds
the training-fold mean residual to the median prior. A separate
type-mean model replaces each training-group median increment with
its mean. Neither uses terrain or another new predictor.
Intercept-only minus median MAE: +0.028 [+0.015, +0.041] m.
Type-mean minus median MAE: +0.044 [+0.027, +0.067] m.
The ridge and LightGBM runs used squared-error objectives but were
judged by MAE. This objective mismatch can explain part of their
deficit; the data do not isolate it from disturbance effects.

## Provenance and limits

Run UTC: 2026-10-15T19:14:15.717859+00:00. Base revision: e660e926e9ac17e095e3136bbdc01b50082347f6.
Exact input hashes, settings and unrounded results are in the JSON.
Rerun: `python scripts/run_posthoc_forest.py` in the project
environment with the local DVC inputs restored.
This is a post hoc analysis, and whole-block intervals omit model
refit variance. It is not an independent preregistered validation.
