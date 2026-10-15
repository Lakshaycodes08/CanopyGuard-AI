# E8 ECHOSAT-to-LiDAR alignment protocol

Status: alignment method implemented and tested; E8 height scoring has not run.
ECHOSAT remains a retrospective product benchmark, never a predictor for the
2013-to-2022 forecast.

## Coordinate systems and operation

The ECHOSAT T10S raster reports WGS 84 / UTM zone 10N (EPSG:32610). The LiDAR
labels use NAD83(2011) / UTM zone 10N (EPSG:6339), with fixed 10 m `cell_id`
centres. `configs/ingestion.yaml:9` is the Sentinel-2 ingestion target CRS;
the ECHOSAT source CRS is documented by its raster and
`reports/echosat_check.md`.

For E8, warp each ECHOSAT band to a raster snapped to the existing LiDAR cell
centres in EPSG:6339. Use the inverse of EPSG operation 9774, "NAD83(2011) to
WGS 84 (1)," with the exact PROJ pipeline pinned in
`configs/product_benchmark.yaml`. Rasterio passes that pipeline explicitly to
GDAL as `COORDINATE_OPERATION`; it does not rely on an implicit CRS match.
Reject any source raster with a different CRS, any unavailable/changed
operation, and any label ID or centre outside the 10 m lattice. Propagate
source nodata, resample continuous height bilinearly, and convert the product's
centimetre values to metres only after resampling. The alignment helper returns
one value per original `cell_id` in label order.

PROJ 9.8.1 selects this EPSG operation for the study box with a **2 m stated
operation accuracy**. Its parameters are zero geocentric translations; at the
study-box centre, the computed EPSG:32610 to EPSG:6339 coordinate difference
is approximately 0.00011 m, due to the ellipsoid change. The 2 m figure is
uncertainty in the datum approximation, not an observed fixed 2 m pixel shift.
The operation does not resolve an unknown product geolocation bias.

## Required E8 sensitivity and reporting

Before comparing product heights to airborne LiDAR, report all nine position
offsets formed from east and north values of -2, 0, and +2 m. The zero-offset
warp is the declared primary alignment. Do not choose an offset by minimizing
LiDAR error; that would tune the benchmark to its truth. Report the range of
scores across offsets as a positional uncertainty sensitivity, alongside the
zero-offset score. Keep identical valid-cell masks where possible and disclose
any count change at raster edges or nodata. Record source raster hash, source
and target CRS, EPSG operation ID and pipeline, PROJ/GDAL versions, resampling,
pixel-centre grid test, and the offset in each E8 output sidecar and report.

PR [#17](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/17) records
Rehaan's account of an email from corresponding author Jan Pauls confirming
bands 1 to 7 as 2018 to 2024. The underlying email is held by Rehaan outside
the repository. The record is still unmerged, so year-specific E8 scoring
remains blocked until PR #17 lands on main. The same reported communication
says that all years are predicted jointly from imagery through 2024. When E8
scores the 2022 band against a single-date 2022 LiDAR survey, label it as a
retrospective joint prediction with access to later imagery. Keep
`echosat.allowed_as_feature: false` regardless of the band-order confirmation.
G2 already passed the **coverage-only** gate; it did not validate ECHOSAT
change or growth accuracy.

## Sources

- `reports/echosat_check.md` and `reports/echosat_coverage.json`: measured
  T10S raster CRS, dimensions, coverage, and the band-order caveat.
- EPSG operation 9774 as shipped in the local PROJ 9.8.1 database; the
  operation name, parameters, accuracy, and remarks were inspected with
  `pyproj.TransformerGroup` using the exact Sonoma study box.
- [GDAL gdalwarp coordinate operation documentation](https://gdal.org/en/stable/programs/gdalwarp.html#cmdoption-gdalwarp-ct)
  describes explicit operation override; Rasterio's
  [reprojection documentation](https://rasterio.readthedocs.io/en/stable/topics/reproject.html)
  describes destination pixel mapping.
