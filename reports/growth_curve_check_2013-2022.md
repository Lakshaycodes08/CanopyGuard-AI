# Growth-prior check, 2013-2022

**Post hoc empirical height ceiling by map class.** The original literature-only A preflight exceeded 0.5% in nine classes. The Chapman-Richards sensitivity uses the maximum of the literature typical-upper value and the 99.5th percentile of max(2013 p95, 2022 p95), calculated within each spatial training fold. The 2022 heights in a held-out fold never set that fold's A. This A is an empirical map-class cutoff, not a biological maximum or a species asymptote. The rule was selected after seeing exceedances and must not be presented as predeclared. Promoting the median increment and treating both forest screens as co-primary were also decisions made after inspecting the earlier curve results.

Run: 2026-10-15T10:11:06.555838+00:00. Issue #8. Base revision: a4e272edbd3ea983348d5a7beb5670ee1791d615.

## Gate G3: co-primary forest median-increment prior

**PASS**: the type-specific or pooled broad-group median increment beats no change on both forest screens when each 95% whole-block interval is entirely below zero.
LiDAR-loss screen off (125,888 cells): median MAE 1.256 m versus no change 1.378 m; median minus no change -0.121 [-0.145, -0.097] m.
LiDAR-loss screen on (76,980 cells): median MAE 0.782 m versus no change 1.049 m; median minus no change -0.268 [-0.312, -0.227] m. This retrospectively selected growth-only subset is an upper bound on performance for undisturbed canopy.
Curve minus median is +0.000 [-0.005, +0.005] m with the LiDAR-loss screen off and +0.002 [-0.007, +0.013] m with it on. Neither establishes a height-dependent advantage.
The co-primary comparisons use five folds, 2 km blocks, 2,000 whole-block bootstrap draws and 8.95825 years between surveys.
The loss-off subset still uses retrospective fire and Hansen screens; it is less conditioned on target-epoch LiDAR but is not a fully prospective 2013 forecast evaluation.

## Forecast growth prior

The selected stage-one prior is the training-group median p95 increment. Mapped classes with fewer than 500 training cells use their broad forest group. These full-sample increments are fitted on the forest LiDAR-loss-off subset for later forecasting; the G3 scores above use held-out-fold medians. Height-bin medians were not tested and require their own held-out comparison before adoption.

| Forest map class | Fit scope | Training cells | Median increment (m) |
| --- | --- | ---: | ---: |
| Quercus agrifolia Alliance | type:Quercus agrifolia Alliance | 25,116 | +0.506 |
| Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | type:Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | 17,665 | +0.347 |
| Quercus douglasii Alliance | type:Quercus douglasii Alliance | 11,777 | +0.356 |
| Quercus lobata Alliance | type:Quercus lobata Alliance | 11,855 | +0.423 |
| Umbellularia californica Alliance | type:Umbellularia californica Alliance | 11,624 | +0.399 |
| Quercus garryana Alliance | type:Quercus garryana Alliance | 7,856 | +0.388 |
| Arbutus menziesii Alliance | type:Arbutus menziesii Alliance | 7,627 | +0.490 |
| Quercus kelloggii Alliance | type:Quercus kelloggii Alliance | 7,982 | +0.706 |
| Pseudotsuga menziesii Alliance | type:Pseudotsuga menziesii Alliance | 5,578 | +1.056 |
| Quercus wislizeni (tree) Alliance | type:Quercus wislizeni (tree) Alliance | 3,636 | +0.665 |
| Populus fremontii Alliance | type:Populus fremontii Alliance | 7,070 | +0.327 |
| Sequoia sempervirens Alliance | type:Sequoia sempervirens Alliance | 2,114 | +1.226 |
| Quercus chrysolepis Alliance | type:Quercus chrysolepis Alliance | 1,520 | +0.641 |
| Hesperocyparis sargentii Alliance | type:Hesperocyparis sargentii Alliance | 1,087 | +0.581 |
| Pinus sabiniana / Quercus durata Provisional Alliance | type:Pinus sabiniana / Quercus durata Provisional Alliance | 1,166 | +1.334 |
| Eucalyptus (globulus, camaldulensis) Semi-natural Alliance | type:Eucalyptus (globulus, camaldulensis) Semi-natural Alliance | 1,335 | +0.751 |
| Pinus attenuata Alliance | type:Pinus attenuata Alliance | 556 | +0.797 |
| Acer macrophyllum Alliance | broad:hardwood forest | 115,387 | +0.441 |

## Selection and A sensitivity

| Scope | A mode | Cells | Blocks | No change MAE | Median MAE | Curve MAE | Median - no change [95% block CI] | Curve - no change [95% block CI] | Curve - median [95% block CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| forest loss on | posthoc | 76,980 | 82 | 1.049 | 0.782 | 0.784 | -0.268 [-0.312, -0.227] | -0.266 [-0.314, -0.220] | +0.002 [-0.007, +0.013] |
| forest loss off | posthoc | 125,888 | 83 | 1.378 | 1.256 | 1.256 | -0.121 [-0.145, -0.097] | -0.121 [-0.147, -0.094] | +0.000 [-0.005, +0.005] |
| all loss on | free | 83,772 | 83 | 1.112 | 0.825 | 0.828 | -0.287 [-0.337, -0.243] | -0.284 [-0.342, -0.230] | +0.004 [-0.008, +0.015] |
| all loss off | free | 140,530 | 84 | 1.479 | 1.358 | 1.355 | -0.121 [-0.142, -0.097] | -0.123 [-0.147, -0.098] | -0.002 [-0.007, +0.003] |
| forest loss on | literature | 76,980 | 82 | 1.049 | 0.782 | 0.794 | -0.268 [-0.312, -0.227] | -0.255 [-0.301, -0.212] | +0.012 [+0.001, +0.025] |
| forest loss on | free | 76,980 | 82 | 1.049 | 0.782 | 0.784 | -0.268 [-0.312, -0.227] | -0.265 [-0.318, -0.216] | +0.002 [-0.009, +0.015] |
| forest loss on | record | 76,980 | 82 | 1.049 | 0.782 | 0.795 | -0.268 [-0.312, -0.227] | -0.254 [-0.301, -0.211] | +0.013 [+0.002, +0.026] |

The LiDAR-loss-off rows keep the fire and Hansen screens. All-class rows are secondary and use the former free-A model because literature A values were specified for forest alliances only. The literature-only row keeps Douglas-fir and redwood at 76 and 91 m. The record-tree row uses 101 and 111 m for those classes; all other classes keep their literature A. The free-A row is the former fit.
If an entire map class lies in a held-out spatial fold, its training fold has no class-specific height percentile. That class uses its literature A for that fold; the affected cells and classes are recorded in the machine metrics. This does not affect the main forest-loss-on 2 km result.

## Spatial sensitivity and mean-height check

| Scope | A mode | Cells | Blocks | No change MAE | Median MAE | Curve MAE | Median - no change [95% block CI] | Curve - no change [95% block CI] | Curve - median [95% block CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| forest loss on, 1000 m | posthoc | 76,980 | 198 | 1.049 | 0.778 | 0.780 | -0.271 [-0.308, -0.240] | -0.269 [-0.307, -0.232] | +0.003 [-0.010, +0.013] |
| forest loss on, 5000 m | posthoc | 76,980 | 18 | 1.049 | 0.784 | 0.790 | -0.266 [-0.319, -0.223] | -0.260 [-0.311, -0.213] | +0.006 [-0.007, +0.023] |
| forest mean, 2 km | literature | 76,980 | 82 | 1.253 | 0.765 | 0.749 | -0.487 [-0.565, -0.423] | -0.504 [-0.581, -0.432] | -0.017 [-0.035, +0.001] |
Absent-class literature-A fallbacks: forest loss off: 1,087 cells (Hesperocyparis sargentii Alliance); forest loss on 5000 m: 1,153 cells (Acer macrophyllum Alliance, Hesperocyparis sargentii Alliance). The primary forest-loss-on 2 km result has zero fallbacks.

## Forest map classes and empirical height ceilings

The post hoc empirical A is fixed within each training fold before fitting k and c. In this curve sensitivity, cells starting at or above A are forced to no growth. Mixed classes use the largest member literature A; pooled fits share k and c while each class keeps its own fold A. The table reports held-out exceedance after wire and 10 m line exclusions. Its share need not equal 0.5%, because held-out blocks can have taller trees.

| Forest map class | Cells | Curve fit scope | Full-fit empirical A (m) | Fold empirical A range (m) | Held-out 2013 p95 >= fold A | k (/yr) | c | No change MAE | Median MAE | Curve MAE | Bound? |
| --- | ---: | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Quercus agrifolia Alliance | 17,265 | type:Quercus agrifolia Alliance | 28.6 | 27.7-29.0 | 59/17265 (0.34%) | 0.0062 | 1.01 | 1.038 | 0.791 | 0.781 | yes |
| Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | 10,875 | type:Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | 30.0 | 30.0-30.2 | 29/10875 (0.27%) | 0.0042 | 1.01 | 0.848 | 0.678 | 0.687 | yes |
| Quercus douglasii Alliance | 8,343 | type:Quercus douglasii Alliance | 20.0 | 20.0-20.0 | 22/8343 (0.26%) | 0.0082 | 10.00 | 0.512 | 0.330 | 0.331 | yes |
| Quercus lobata Alliance | 7,437 | type:Quercus lobata Alliance | 29.5 | 28.8-29.7 | 23/7437 (0.31%) | 0.0065 | 1.01 | 1.081 | 0.846 | 0.833 | yes |
| Umbellularia californica Alliance | 7,096 | type:Umbellularia californica Alliance | 40.0 | 36.7-40.8 | 38/7096 (0.54%) | 0.0050 | 10.00 | 0.978 | 0.786 | 0.800 | yes |
| Quercus garryana Alliance | 4,597 | type:Quercus garryana Alliance | 31.0 | 30.1-31.0 | 21/4597 (0.46%) | 0.0059 | 10.00 | 0.800 | 0.621 | 0.642 | yes |
| Arbutus menziesii Alliance | 4,512 | type:Arbutus menziesii Alliance | 40.0 | 40.0-40.0 | 5/4512 (0.11%) | 0.0059 | 10.00 | 1.075 | 0.793 | 0.808 | yes |
| Quercus kelloggii Alliance | 4,464 | type:Quercus kelloggii Alliance | 41.4 | 37.8-42.7 | 42/4464 (0.94%) | 0.0078 | 10.00 | 1.336 | 0.920 | 0.953 | yes |
| Pseudotsuga menziesii Alliance | 3,322 | type:Pseudotsuga menziesii Alliance | 76.0 | 76.0-76.0 | 0/3322 (0.00%) | 0.0041 | 1.45 | 1.876 | 1.261 | 1.256 | no |
| Quercus wislizeni (tree) Alliance | 3,036 | type:Quercus wislizeni (tree) Alliance | 23.0 | 23.0-23.4 | 3/3036 (0.10%) | 0.0107 | 10.00 | 1.050 | 0.687 | 0.721 | yes |
| Populus fremontii Alliance | 1,433 | type:Populus fremontii Alliance | 34.0 | 34.0-34.0 | 0/1433 (0.00%) | 0.0105 | 1.01 | 2.152 | 1.459 | 1.437 | yes |
| Sequoia sempervirens Alliance | 1,217 | type:Sequoia sempervirens Alliance | 91.0 | 91.0-91.0 | 0/1217 (0.00%) | 0.0036 | 1.35 | 2.280 | 1.683 | 1.675 | no |
| Quercus chrysolepis Alliance | 1,111 | type:Quercus chrysolepis Alliance | 32.0 | 30.0-33.2 | 10/1111 (0.90%) | 0.0066 | 2.27 | 0.982 | 0.658 | 0.672 | no |
| Hesperocyparis sargentii Alliance | 982 | type:Hesperocyparis sargentii Alliance | 23.0 | 23.0-23.0 | 0/982 (0.00%) | 0.0087 | 10.00 | 0.747 | 0.880 | 0.465 | yes |
| Pinus sabiniana / Quercus durata Provisional Alliance | 492 | broad:conifer forest | 29.8 | 27.8-30.5 | 2/492 (0.41%) | 0.0049 | 2.05 | 2.096 | 1.287 | 1.732 | no |
| Eucalyptus (globulus, camaldulensis) Semi-natural Alliance | 342 | broad:hardwood forest | 55.0 | 55.0-55.0 | 0/342 (0.00%) | 0.0066 | 3.00 | 2.276 | 1.918 | 1.772 | no |
| Pinus attenuata Alliance | 285 | broad:conifer forest | 28.7 | 24.1-31.3 | 5/285 (1.75%) | 0.0049 | 2.05 | 2.361 | 1.647 | 1.978 | no |
| Acer macrophyllum Alliance | 171 | broad:hardwood forest | 28.4 | 27.4-28.5 | 0/171 (0.00%) | 0.0066 | 3.00 | 1.717 | 1.298 | 1.295 | no |

Fitted k/c bound warnings: Quercus agrifolia Alliance, Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance, Quercus douglasii Alliance, Quercus lobata Alliance, Umbellularia californica Alliance, Quercus garryana Alliance, Arbutus menziesii Alliance, Quercus kelloggii Alliance, Quercus wislizeni (tree) Alliance, Populus fremontii Alliance, Hesperocyparis sargentii Alliance.
11 of 18 class fits touch a k or c bound. Their fitted shape parameters should not be interpreted biologically. Literature-only and record-tree A curves are worse than the type-median baseline at their 95% intervals; the post hoc curve ties it. Do not tune the curve further or use its shape as the growth prior.

## Curve-shape diagnostic, not ecological support

The 10 m versus 20 m check partly follows from forcing no growth when starting height reaches A. Quercus douglasii has A = 20 m, so its 20 m gain is zero by construction. Nearly flat gains and the mixed Eucalyptus reversal also limit interpretation. A 'shorter gains more' entry does not validate tree biology.

| Forest map class | Gain at 10 m | Gain at 20 m | Shorter gains more? |
| --- | ---: | ---: | --- |
| Quercus agrifolia Alliance | 0.99 m | 0.46 m | yes |
| Quercus (agrifolia, douglasii, garryana, kelloggii, lobata, wislizenii) Alliance | 0.73 m | 0.37 m | yes |
| Quercus douglasii Alliance | 0.52 m | 0.00 m | yes |
| Quercus lobata Alliance | 1.09 m | 0.53 m | yes |
| Umbellularia californica Alliance | 0.67 m | 0.63 m | yes |
| Quercus garryana Alliance | 0.63 m | 0.46 m | yes |
| Arbutus menziesii Alliance | 0.79 m | 0.75 m | yes |
| Quercus kelloggii Alliance | 1.09 m | 1.05 m | yes |
| Pseudotsuga menziesii Alliance | 1.65 m | 1.62 m | yes |
| Quercus wislizeni (tree) Alliance | 0.82 m | 0.26 m | yes |
| Populus fremontii Alliance | 2.14 m | 1.25 m | yes |
| Sequoia sempervirens Alliance | 1.83 m | 1.81 m | yes |
| Quercus chrysolepis Alliance | 0.89 m | 0.60 m | yes |
| Hesperocyparis sargentii Alliance | 0.67 m | 0.21 m | yes |
| Pinus sabiniana / Quercus durata Provisional Alliance | 0.63 m | 0.38 m | yes |
| Eucalyptus (globulus, camaldulensis) Semi-natural Alliance | 1.38 m | 1.42 m | no |
| Pinus attenuata Alliance | 0.60 m | 0.34 m | yes |
| Acer macrophyllum Alliance | 0.74 m | 0.43 m | yes |

![Fitted growth curves](figures/growth_curves_2013-2022.png)

## Evidence and limits

The original clean screen retained 111,672 of 1,478,103 label cells. The revised selections and wire exclusions are recorded in the machine metrics and preflight JSON.
2013 vegetation groups come from the [Sonoma Veg Map](https://socogis.sonomacounty.ca.gov/map/rest/services/OWTSPublic/Sonoma_Veg_Map_Vegetation_and_Habitat/MapServer/0/query); fire from [FRAP](https://services.arcgis.com/V6ZHFr6zdgNZuVG0/ArcGIS/rest/services/California_Fire_Perimeters/FeatureServer/0/query) and [MTBS](https://apps.fs.usda.gov/ArcX/rest/services/EDW/EDW_MTBS_01/MapServer/63/query); Hansen supplies [loss year](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/Hansen_GFC-2024-v1.12_lossyear_40N_130W.tif).
Sonoma MAP_CLASS is a mapping unit, not a species-pure cell label. Several empirical map-class A values exceed the cited typical-upper species heights. Taller crowns of other species within polygons and residual LiDAR outliers are possible explanations, not verified causes. The empirical A is not a biological ceiling.
The Acer macrophyllum literature A of 27 m uses a 2011 Oregon champion tree, an explicit exception to the typical-upper source rule. Held-out Acer exceedance was 0/171; the class uses broad:hardwood forest for curve fitting.
Whole-block bootstrap intervals resample spatial blocks while holding the fitted fold models fixed; they omit refit variance and may therefore be too narrow.
The LiDAR-loss screen selects a retrospective subset; it is never a forecast feature. No random visual audit of persistent forest cells has been completed. Fire, Hansen and LiDAR screens alone do not verify continuous undisturbed forest, so the growth-only sample and its upper-bound interpretation remain provisional.
The mixed Eucalyptus literature A is 55 m from FEIS E. globulus. Kew and ANBG describe E. camaldulensis up to 45 m in its native Australian range; a person still needs to verify the Jepson entry. The exact excerpts and source dates are in reports/claims_log.md.
An offline test changes a held-out fold's 2022 heights and confirms that fold's A and predictions do not change. Claude Opus 5 reviewed the A-rule implementation at 32b94cefc8e6530ed4fe65c751f10b96e77319e0 during 2026-10-15T09:54:00Z/2026-10-15T10:04:00Z (https://claude.ai/code/session_01E86qLp2sVy4PU2mBmrPa3E). This was an AI code spot-check by a reviewer who proposed the rule, not an independent human review; human sign-off remains pending.

## Reproduction

Run scripts/join_sonoma_veg.py, scripts/build_clean_cells.py, scripts/flag_wire_suspects.py, then scripts/run_growth_curve_check.py with the configured environment. Local inputs and hashes are listed in the machine metrics and provenance files.
