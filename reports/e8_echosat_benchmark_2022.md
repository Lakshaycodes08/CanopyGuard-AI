# E8 ECHOSAT 2022 product benchmark

Configured 2022 band: 5 of 7. Source heights were converted from stored
centimetres to metres after bilinear resampling.
ECHOSAT 2022 is a retrospective joint prediction informed by imagery
through 2024. This compares modeled height with
single-date 2022 airborne LiDAR p95 on existing 10 m cells.
It is cross-product disagreement, not a forecast,
growth-rate validation, or proof of product bias.
ECHOSAT is not a model feature.

## Primary zero-offset comparison

Cells: 1,444,284; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 3.951 | [3.724, 4.189] |
| Median signed error | 2.539 | [2.153, 2.724] |
| Mean signed error | 2.475 | [2.273, 2.695] |
| Root mean squared error | 5.150 | [4.897, 5.407] |

The primary mask retains fire, Hansen-loss, and LiDAR-loss cells. It removes
disputed overlaps, nonfinite p95 labels, PR #13 max/p95 wire exclusions,
and product nodata. LiDAR p95 and modeled product height are related but
different height summaries.

## Exclusions

| Step | Cells |
| --- | ---: |
| label cells | 1,478,103 |
| disputed overlap | 198 |
| nonfinite p95 after overlap | 0 |
| wire excluded after overlap and p95 | 33,621 |
| before product nodata | 1,444,284 |
| product nodata zero offset | 0 |

## Fixed position shifts

All 9 preregistered east/north shifts (-2, 0, 2 m) use the same
1,444,284 valid cells. No shift was
selected by agreement with LiDAR. The range is a positional sensitivity,
not a confidence interval.

| Metric (m) | Lowest | Highest |
| --- | ---: | ---: |
| Mean absolute error | 3.942 | 4.011 |
| Median signed error | 2.539 | 2.555 |
| Mean signed error | 2.473 | 2.477 |
| Root mean squared error | 5.129 | 5.215 |

| East shift (m) | North shift (m) | Cells lost to nodata | MAE (m) |
| ---: | ---: | ---: | ---: |
| -2 | -2 | 0 | 3.960 |
| -2 | 0 | 0 | 3.942 |
| -2 | 2 | 0 | 3.963 |
| 0 | -2 | 0 | 3.968 |
| 0 | 0 | 0 | 3.951 |
| 0 | 2 | 0 | 3.972 |
| 2 | -2 | 0 | 4.006 |
| 2 | 0 | 0 | 3.990 |
| 2 | 2 | 0 | 4.011 |

## Resolution sensitivity

### 30 m bins

Contributing paired 10 m cells: 1,412,495.
Occupancy distribution (cells per bin: bin count): {'5': 2520, '6': 9713, '7': 5284, '8': 8894, '9': 137053}.

Cells: 163,464; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 3.223 | [3.032, 3.427] |
| Median signed error | 2.472 | [2.195, 2.675] |
| Mean signed error | 2.489 | [2.288, 2.708] |
| Root mean squared error | 4.011 | [3.801, 4.224] |

### 100 m bins

Contributing paired 10 m cells: 1,388,317.
Occupancy distribution (cells per bin: bin count): {'50': 171, '51': 19, '52': 17, '53': 16, '54': 25, '55': 25, '56': 23, '57': 21, '58': 54, '59': 81, '60': 295, '61': 36, '62': 41, '63': 45, '64': 33, '65': 41, '66': 36, '67': 40, '68': 82, '69': 67, '70': 263, '71': 63, '72': 66, '73': 67, '74': 88, '75': 116, '76': 136, '77': 152, '78': 179, '79': 231, '80': 510, '81': 83, '82': 92, '83': 108, '84': 104, '85': 127, '86': 128, '87': 149, '88': 180, '89': 190, '90': 557, '91': 205, '92': 195, '93': 222, '94': 232, '95': 269, '96': 329, '97': 441, '98': 559, '99': 909, '100': 7025}.

Cells: 15,143; 2 km blocks: 126.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 2.755 | [2.568, 2.943] |
| Median signed error | 2.416 | [2.174, 2.622] |
| Mean signed error | 2.483 | [2.270, 2.696] |
| Root mean squared error | 3.269 | [3.062, 3.466] |

## Reference-height strata

Primary cells below the first stratum: 0.

### LiDAR p95 [0,2) m

Cells: 563,055; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 4.302 | [3.899, 4.763] |
| Median signed error | 3.400 | [2.868, 4.066] |
| Mean signed error | 4.302 | [3.899, 4.763] |
| Root mean squared error | 5.362 | [4.973, 5.776] |


### LiDAR p95 [2,5) m

Cells: 176,900; 2 km blocks: 129.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 4.559 | [4.183, 4.938] |
| Median signed error | 3.978 | [3.443, 4.415] |
| Mean signed error | 4.524 | [4.136, 4.907] |
| Root mean squared error | 5.733 | [5.416, 6.064] |


### LiDAR p95 [5,10) m

Cells: 200,276; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 3.773 | [3.532, 4.014] |
| Median signed error | 2.861 | [2.544, 3.159] |
| Mean signed error | 3.197 | [2.873, 3.510] |
| Root mean squared error | 4.870 | [4.587, 5.158] |


### LiDAR p95 [10,20) m

Cells: 409,008; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 2.817 | [2.675, 2.998] |
| Median signed error | 0.237 | [-0.038, 0.482] |
| Mean signed error | 0.405 | [0.110, 0.691] |
| Root mean squared error | 3.718 | [3.501, 3.990] |


### LiDAR p95 [20,30) m

Cells: 74,567; 2 km blocks: 129.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 4.893 | [4.697, 5.120] |
| Median signed error | -3.663 | [-4.147, -3.117] |
| Mean signed error | -3.437 | [-4.004, -2.869] |
| Root mean squared error | 6.020 | [5.789, 6.283] |


### LiDAR p95 [30,inf) m

Cells: 20,478; 2 km blocks: 112.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 9.992 | [9.159, 10.939] |
| Median signed error | -8.749 | [-9.747, -7.799] |
| Mean signed error | -9.641 | [-10.700, -8.653] |
| Root mean squared error | 12.495 | [11.517, 13.608] |

Binning on the reference can make signed errors near interval boundaries
look like regression toward the mean. These strata are descriptive.

## Secondary max-height reference

Common p95/max/product valid cells: 1,444,284.

Cells: 1,444,284; 2 km blocks: 130.

| Metric (m) | Estimate | 95% whole-block interval |
| --- | ---: | ---: |
| Mean absolute error | 3.669 | [3.469, 3.879] |
| Median signed error | 1.562 | [1.366, 1.868] |
| Mean signed error | 1.434 | [1.264, 1.614] |
| Root mean squared error | 4.909 | [4.666, 5.154] |

This checks sensitivity to the LiDAR height summary, not absolute bias.

## Reproducibility and scope

Git revision: `d2e6624c4fd727aeb5527595ead92148fb2cba00`.
Source: https://echosat.uni-muenster.de/ECHOSAT_T10S.tif
Band order: J. Pauls (corresponding author), personal communication, October 2026.
Intervals use 2,000 whole 2 km block draws with seed 42.

The raster hash below identifies the local study-box copy. Its provenance
records the original tile URL and download time.

| Input | SHA-256 |
| --- | --- |
| raster | `c8ba58c329b68cb38d51690db173f4b4c34c8ae99a3ac14b990c03581600c9ad` |
| labels | `f54aac5817cf9825d28649e0bbb96f8ae14ac653d1601ef8e2b4a2f26c6aabe9` |
| wire_flags | `26f6672d2c10240da6fb62a0e508e2e018b8bc43d95342d6de798e8d23566bee` |
| benchmark_config | `5f369c26be7ad77cfba728d433e9b7ca8332de417d94cba82c4436ade9a63a1c` |
| ingestion_config | `70dc2355e1dbef1981e9e34ac913d29997cbc5e1f7ebb650aa86572de975f823` |
| forecasting_config | `08bea713cd9feadd49a45436765bb5937379d137a3c71287e8881f9c8a2d64f5` |
| study_area_config | `2e52e7212e23c8cceba910c0453447d99f9edcf6476ee885766d2eadb59ab512` |

Source CRS: EPSG:32610; target CRS: EPSG:6339.
EPSG operation: 9774 (Inverse of UTM zone 10N + Inverse of NAD83(2011) to WGS 84 (1) + UTM zone 10N).
Explicit PROJ pipeline: `+proj=pipeline +step +inv +proj=utm +zone=10 +ellps=WGS84 +step +proj=utm +zone=10 +ellps=GRS80`.
PROJ: 9.5.1; GDAL: 3.10.3.
Resampling: bilinear; 10 m cell grid checked: True.
The 2 m stated operation accuracy is datum uncertainty,
not a measured pixel shift.
ECHOSAT 2018-2022 modeled change and LiDAR 2013-2022 change span
different intervals and are not compared as interchangeable growth evidence.
