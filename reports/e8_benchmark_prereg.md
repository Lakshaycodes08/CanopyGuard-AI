# E8 ECHOSAT 2022 product benchmark preregistration

Status: pre-score analysis plan. The initial plan was pushed as `e660e92`;
the 16 October 2026 amendment below must also be pushed before any E8 height
score. No E8 height score has run. This file and
`configs/product_benchmark.yaml` must be on GitHub before scoring.
Year-specific scoring also waits until PR #17, which records the author-confirmed
band order and joint-prediction design, merges into main.

Status update (2026-10-20): PRs #17 and #18 merged on 2026-10-17; the pre-score plan below is unchanged.

## Question and estimand

Describe agreement between the ECHOSAT 2022 canopy-height map and a
single-date 2022 airborne-LiDAR p95 canopy-height summary on the study's
existing 10 m cells. This is a retrospective cross-product comparison, not a
2013 forecast, a growth-rate validation, or a pass/fail gate. ECHOSAT predicts
all years jointly from imagery through 2024, so the 2022 band has access to
later observations. It must never be described as a 2022-only estimate.
ECHOSAT remains a benchmark; `echosat.allowed_as_feature` stays false.

## Fixed sources and analysis population

- Product: the ECHOSAT T10S GeoTIFF configured in `configs/ingestion.yaml`.
  Resolve the 2022 band from that config's author-confirmed year list only
  after PR #17 merges. Convert stored centimetres to metres after resampling.
- Reference: `p95_end` for the 2022 survey in
  `data/processed/labels_2013-2022_unique.npz`, joined one-to-one by
  `cell_id`. Exclude disputed overlaps, nonfinite p95 labels, and every
  `exclude_max_p95` cell in the PR #13 wire-flag archive. Apply the same
  max/p95 exclusion rule used by G3; do not select cells based on the observed
  ECHOSAT error. Retain fire, Hansen-loss, and LiDAR-loss cells in the primary
  population. ECHOSAT nodata is excluded after the warp, with excluded counts
  reported separately.
- The primary valid-cell mask is fixed by label quality, wire flags, and
  product nodata. Report 2013 forest-map-class results only as a descriptive
  stratum, never as a replacement primary population. No threshold or
  subgroup may be chosen after seeing E8 errors.

LiDAR p95 and the ECHOSAT product's modeled height are related but not
identical measurement constructs. Their difference is cross-product
disagreement, not automatically product bias or a 2022 growth error.

## Alignment and score

Use the exact EPSG:32610-to-EPSG:6339 operation, bilinear resampling, source
nodata rule, cell-centre test, and 10 m label IDs in
`reports/e8_alignment_protocol.md`. The zero-offset warp is primary.
Prespecify the nine east/north positions from -2, 0, and +2 m. Keep the
intersection of valid cells across all offsets for the primary sensitivity
comparison; also report how many cells each offset loses. Do not select an
offset by matching the LiDAR truth.

Report cell-weighted mean absolute error (MAE), median signed
ECHOSAT-minus-LiDAR error, mean signed error, and root mean squared error, all
in metres. Use 2 km spatial blocks and 2,000 whole-block bootstrap draws with
seed 42 for 95% descriptive intervals. Report the nine-offset range for each
metric. There is no success threshold or model choice based on this result.

## Pre-score amendment: resolution, height, and reference sensitivities

The following analyses were added on 16 October 2026, before any E8 score.
They are descriptive sensitivities. They cannot replace the primary 10 m,
zero-offset p95 result, and no result may be selected by its agreement.

- **Resolution:** At the zero offset only, aggregate the *same paired valid
  10 m cells* into fixed 30 m and 100 m square bins in EPSG:6339. Anchor bin
  edges to the southwest outer edge of the full 10 m label grid (minimum
  label-cell centre minus 5 m in each axis), before any exclusions. A bin is
  eligible when at least half its possible 10 m cells are paired and valid:
  at least 5 of 9 at 30 m or 50 of 100 at 100 m. Average ECHOSAT and p95
  separately over exactly those cells, then score one paired mean per bin
  with equal bin weights. Use the same four metrics and 2 km block bootstrap,
  assigning each bin by its centre. Report eligible bin count, contributing
  10 m cell counts, and the occupancy distribution. These are E8 resolution
  sensitivities only; G3 and stage two retain their existing 10 m study unit.
- **Reference-height strata:** For the primary zero-offset 10 m result, group
  paired cells by LiDAR `p95_end` in the fixed intervals [0,2), [2,5),
  [5,10), [10,20), [20,30), and [30,infinity) metres. Report cell and block
  counts and the four metrics in each interval, with the same block bootstrap
  intervals when at least two blocks contribute. Flag an interval with fewer
  than two blocks as too sparse for an interval estimate. These are
  conditional descriptions, not independently sampled tests. Binning on the
  reference can make signed errors near bin edges appear to regress toward
  the mean; do not interpret that pattern alone as height-dependent bias.
- **Secondary height reference:** At the zero offset and 10 m resolution,
  repeat the four metrics against `max_end` from the same LiDAR archive. Use
  only cells with both finite `p95_end` and `max_end`, the same disputed-overlap
  and `exclude_max_p95` wire exclusions, and valid ECHOSAT values; report the
  paired common-mask count. Use the same 2 km block bootstrap. This checks
  sensitivity to the LiDAR height summary; it does not replace p95 as the
  primary reference or establish a product's absolute bias.

Temporal change is outside this benchmark. In particular, ECHOSAT's
2018-to-2022 modeled difference and LiDAR's 2013-to-2022 difference have
different intervals, so E8 will not score them as interchangeable change
estimates. This limitation must be stated in the E8 report.

The output JSON and report must record the Git revision; source raster,
reference archive, wire archive and config hashes; source and target CRS;
EPSG operation and pipeline; PROJ/GDAL versions; resampling; 10 m cell-grid
test; each offset; nodata and exclusion counts; sensitivity bin, stratum, and
common-mask counts; and the fact that 2022 is a joint prediction informed
through 2024. The referenced raster and labels remain outside Git.

## Analysis boundary

This preregistration fixes the benchmark before scoring. It does not change
G2's coverage-only PASS or the G3 and stage-two decisions. A failure to meet
the specified input, CRS, or provenance checks stops E8 rather than triggering
an unrecorded alternative alignment.
