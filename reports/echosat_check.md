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
  lon/lat. Any later stage must do the same and not compare raw coordinates.
- Band order is inferred, not documented. The authors do not label the 7 bands.
  The repo reads them as 2018 to 2024 in order. Evidence for that order:
  - Large drops and large gains are very unbalanced. Summed over consecutive
    steps there are 35,451 pixels that lose more than 5 m and 290 that gain more
    than 5 m (`abrupt_changes` in `reports/echosat_coverage.json`). The model
    forces slow growth and allows abrupt loss only for disturbance, so this
    fits a forward order.
  - Manual check, not in the repo: the CAL FIRE FRAP perimeter for the Kincade
    fire (alarm 2019-10-23, 77,762 acres) covers 41.8 percent of the box. About
    94 percent of the large drops between the 2019 and 2020 bands fall inside it,
    and about 8 percent of the few large drops between the 2018 and 2019 bands do.
  - This supports the order but does not prove it. Confirm with the authors
    before relying on a single year.
- Smooth by design: the model constrains yearly slopes to 0 to 3 m per year
  (paper, section 3.3), so slow change is a modeling choice. Typical error
  against GEDI is about 5 to 6 m (paper), larger than a year of growth.
- No bare ground: the lowest height in every year is about 2 m, never 0.
- Fire and logging loss is visible. Gradual growth is not established. The
  authors state that year-to-year change has no direct validation against
  independent repeated observations (paper, section 5.1).
- 2023: GEDI was offline from 2023-03-17 to 2024-04-22, which the paper links to
  a different label pattern and accuracy in 2023. 2018 has no GEDI labels.
- Large post-fire drops keep appearing inside the Kincade perimeter in later
  years. They may be tree death, salvage logging, or model noise. Not resolved.

## Not established here

- No comparison with repeat airborne LiDAR, so no claim about growth accuracy.
- ECHOSAT years after the 2022 target survey must not become predictors for a
  forecast scored on 2022 LiDAR. The leakage guard in
  `tests/test_truth_isolation.py` does not list ECHOSAT yet. Follow-up for the
  feature-table work.

## Reproduce

`python scripts/check_echosat.py` needs network access to
`echosat.uni-muenster.de`. Tests are offline: `python -m pytest tests/test_echosat.py`.
The sample figure `reports/figures_sample/echosat_sample.png` is committed on
purpose. `reports/figures/` is gitignored for generated outputs, so this small
folder holds the one picture a reviewer needs to see. The same command
regenerates it.
