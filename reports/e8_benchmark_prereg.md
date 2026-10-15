# E8 ECHOSAT 2022 product benchmark preregistration

Status: frozen analysis plan; no E8 height score has run. This file and
`configs/product_benchmark.yaml` must be pushed to GitHub before any E8 score.
Year-specific scoring also waits until PR #17, which records the author-confirmed
band order and joint-prediction design, merges into main.

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

The output JSON and report must record the Git revision; source raster,
reference archive, wire archive and config hashes; source and target CRS;
EPSG operation and pipeline; PROJ/GDAL versions; resampling; 10 m cell-grid
test; each offset; nodata and exclusion counts; and the fact that 2022 is a
joint prediction informed through 2024. The referenced raster and labels
remain outside Git.

## Analysis boundary

This preregistration fixes the benchmark before scoring. It does not change
G2's coverage-only PASS or the G3 and stage-two decisions. A failure to meet
the specified input, CRS, or provenance checks stops E8 rather than triggering
an unrecorded alternative alignment.
