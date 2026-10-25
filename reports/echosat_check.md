# ECHOSAT 2018-2023 coverage check

Issue: https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/7
Run date: 2026-10-12. Owner: Rehaan.

## Result

Pass for coverage. The maps download, and 2018-2023 hold real values over the
whole configured study box. This is a coverage check only. ECHOSAT is a modeled
height product, and it is **not** a validated growth signal until its height
differences are checked against repeat airborne LiDAR.

## Product and access

- Citation: Pauls et al. 2026, ECHOSAT: Estimating Canopy Height Over Space And
  Time, arXiv:2602.21421 (https://doi.org/10.48550/arXiv.2602.21421).
- Version: the authors publish no version number. The file is dated
  2026-02-21 on the server (ETag `"699a3ad4-bdd8ce39e"`, 50,961,638,302 bytes).
- Licence stated by the authors: CC-BY 4.0 for the maps.
- Index: https://echosat.uni-muenster.de/ (Sentinel-2 grid tiles).
- Tile holding the study box: https://echosat.uni-muenster.de/ECHOSAT_T10S.tif
- Format: LZW GeoTIFF, 7 bands, int16 centimeters, 10 m pixels, EPSG:32610,
  nodata -9999. Also published as the Earth Engine asset
  `projects/ai4forest/assets/echosat`.
- Local download command (reads only the study box, not the 47 GB tile):

```
python scripts/check_echosat.py
```

It writes `data/interim/echosat/echosat_box.tif` (68 MB, gitignored, with a
provenance sidecar), `reports/echosat_coverage.json`, and the sample figure
`reports/figures_sample/echosat_sample.png`.
All settings come from the `echosat:` section of `configs/ingestion.yaml` and
the box from `configs/study_area.yaml`.

## Catalogue overlap versus usable values

- Catalogue overlap: the server index lists the tile, and the raster footprint
  contains the whole study box (`raster_footprint_covers_box: true`).
- Usable values: pixels were counted only where the pixel centre lies inside the
  lon/lat box and the value is not the nodata value. The two answers agree here,
  but they are checked separately.

## Valid pixels per year inside the study box

Study box: 5,330,171 pixels, 533.0171 km2 (10 m pixels, pixel-centre test in
lon/lat).

| Year | Valid pixels | Valid share | Median height (m) | 95th percentile (m) | Max (m) |
| --- | --- | --- | --- | --- | --- |
| 2018 | 5,330,171 | 100% | 9.13 | 21.93 | 47.51 |
| 2019 | 5,330,171 | 100% | 9.19 | 21.97 | 47.54 |
| 2020 | 5,330,171 | 100% | 9.20 | 21.84 | 47.48 |
| 2021 | 5,330,171 | 100% | 9.21 | 21.85 | 48.13 |
| 2022 | 5,330,171 | 100% | 9.21 | 21.73 | 47.55 |
| 2023 | 5,330,171 | 100% | 9.15 | 21.68 | 47.65 |

No missing year, no partial coverage, no nodata pixels in the box. The product
also holds a 2024 band, which is outside this check.

## Caveats

- Projection mismatch: the study config is lon/lat (EPSG:4326) and the raster is
  UTM zone 10N (EPSG:32610). The check handles it by testing pixel centres in
  lon/lat. LiDAR labels use EPSG:6339, so E8 must use the pinned operation and
  pixel-centre alignment in `reports/e8_alignment_protocol.md`; raw projected
  coordinates must not be treated as the same grid.
- Band order: the files do not name the bands, but Jan Pauls, the corresponding
  author of the paper, confirmed by email (October 2026) that bands 1 to 7 are
  2018 to 2024 in order (J. Pauls, personal communication). The same email is
  the source for the next two points.
  Two checks in this repo agree, and both rerun with `scripts/check_echosat.py`:
  - Large drops and large gains are very unbalanced. Summed over consecutive
    steps there are 35,451 pixels that lose more than 5 m and 290 that gain more
    than 5 m (`abrupt_changes` in `reports/echosat_coverage.json`). The model
    forces slow growth and allows abrupt loss only for disturbance, so this
    fits a forward order.
  - Fire check (`fire_check` in the JSON): the CAL FIRE FRAP perimeter of the
    Kincade fire (alarm 2019-10-23, 77,762 acres) covers 41.8 percent of the box
    pixels. Of the 16,733 large drops in the 2019 to 2020 step, 15,694 (93.8
    percent) fall inside it. In the 2018 to 2019 step only 21 of 269 (7.8
    percent) do. The step with the most drops inside the perimeter is the
    expected one, 2019 to 2020. FRAP states its perimeters can be incomplete or
    over-generalized.
- Joint prediction: the model predicts all years in one pass, so a year's map
  uses the imagery of the surrounding years too, including later ones (author
  email). Years are not independent maps. The authors did not say why a
  late-2019 fire first shows in the 2020 band, so the fire check only relies on
  which step has the most drops.
- Independence: the authors used only GEDI for training and validation, no
  airborne LiDAR, so a comparison with airborne LiDAR is independent of the
  training labels.
- Smooth by design: the model constrains yearly slopes to 0 to 3 m per year
  (paper, section 3.3), so slow change is a modeling choice. Typical error
  against GEDI is about 5 to 6 m (paper), larger than a year of growth.
- No bare ground: the lowest height in every year is between 1.79 m and 2.24 m,
  never 0, so bare ground and vineyards read as short canopy. The LiDAR
  comparison must report cells with LiDAR height below 2 m separately.
- Fire and logging loss is visible. Gradual growth is not established. The
  authors state that year-to-year change has no direct validation against
  independent repeated observations (paper, section 5.1).
- 2023: GEDI was offline from 2023-03-17 to 2024-04-22, which the paper links to
  a different label pattern and accuracy in 2023. 2018 has no GEDI labels.
- Large post-fire drops keep appearing inside the Kincade perimeter in later
  years. They may be tree death, salvage logging, or model noise. Not resolved.

## Not established here

- No comparison with repeat airborne LiDAR, so no claim about growth accuracy.
- ECHOSAT is covered by the leakage guard and is a benchmark only.
  Because every year is predicted from imagery through 2024, even the 2018 band
  carries information from after any real prediction cutoff.
  `select_echosat_feature_years` in `src/canopyguard/features/lidar.py` admits
  no ECHOSAT year while `echosat.allowed_as_feature` is false in
  `configs/ingestion.yaml` (the default). If it is switched on, a year is still
  admitted only when 31 December 2024 is on or before the cutoff, and the
  cutoff must precede the target survey, so no real forecast can use it as a
  feature. Feature, forecasting, and risk code also cannot import the raw
  ECHOSAT modules (`tests/test_truth_isolation.py`).

## Reproduce

`python scripts/check_echosat.py` needs network access to
`echosat.uni-muenster.de`. Tests are offline: `python -m pytest tests/test_echosat.py
tests/test_echosat_fire.py tests/test_truth_isolation.py`.
The sample figure `reports/figures_sample/echosat_sample.png` is committed on
purpose. `reports/figures/` is gitignored for generated outputs, so this small
folder holds the one picture a reviewer needs to see. It is downsampled
to stay under 0.3 MB. The same command regenerates it.
