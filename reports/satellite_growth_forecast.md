# Satellite-only canopy growth forecast: results and limits

Run date: 2026-10-19. All numbers come from the JSON files named below and can
be regenerated with the commands at the end. This is a research result, not a
clearance or safety determination.

## Question

Can data available before a cutoff date (Landsat history, terrain, climate
normals, a satellite-based ecosystem map) predict nine-year canopy height change
that repeat airborne LiDAR later measured, without any airborne survey as an
input? LiDAR supplies the labels and the grading only.

## Setup

- Labels: 2013 to 2022 LiDAR canopy change, 10 m cells, averaged to 30 m pixels
  and 90 m blocks. Cutoff for all predictors: 2013-09-27, the day before the 2013
  survey started.
- Regions: the original study box and two neighbouring boxes (west, east), built
  with the same label pipeline. Unique valid label cells: 1,478,103 (study),
  923,611 (west), 965,770 (east).
- Predictors: Landsat 5/7/8 summer composites 2001-2013, NASADEM terrain,
  TerraClimate 1981-2010 normals, USGS GAP/LANDFIRE 2011 ecosystems. The Sonoma
  vegetation map was kept only as a comparison, because its attributes are
  partly derived from airborne LiDAR.
- Test: leave one region out. Train on two regions, score the third. Test pixels
  within 3 km of another region are not scored. Intervals use a paired bootstrap
  that resamples 5 km blocks.

## Finding 1: a plain regression on net change mostly learns fire

Between the two surveys, 48 percent (study), 40 percent (west) and 81 percent
(east) of pixel area at 90 m falls inside CAL FIRE perimeters with alarm dates
after the first survey (mean burned share, `data/processed` growth tables).
Mean net change over all pixels was -0.35, -0.39 and -1.43 m. Over the pixels
that pass the screen below it was +0.40, +0.76 and +0.80 m.

With every pixel included and a whole region held out, the satellite-only model
did not beat guessing no change: typical error 0.78 vs 0.68 m (study), 2.20 vs
1.52 m (west), 1.94 vs 2.03 m (east), Landsat-only model vs no change
(`reports/growth_region_transfer.json`, scale x3, screen `all`). Earlier
within-study results on all pixels mixed fire patterns with growth and should
not be read as growth skill.

Fire after 2013 cannot be seen in data dated before 2013.

## Finding 2: steady growth transfers to unseen regions

Screen `undisturbed`: no fire perimeter dated between the surveys and LiDAR loss
share at most 0.1. Typical error in metres at 90 m, region held out:

| Method | Study | West | East |
| --- | --- | --- | --- |
| No change | 0.479 | 0.837 | 0.902 |
| Constant average growth | 0.528 | 0.615 | 0.671 |
| Growth by ecosystem type | 0.392 | 0.537 | 0.589 |
| Survey height and ecosystem growth curve (uses 2013 LiDAR) | 0.372 | 0.503 | 0.552 |
| Satellite only, Landsat | 0.354 | 0.464 | 0.449 |
| Satellite only, Landsat + terrain + ecosystem | 0.351 | 0.453 | 0.470 |
| Satellite + survey height (comparison, uses 2013 LiDAR) | 0.336 | 0.447 | 0.457 |

Scored pixels: 5,137 / 3,877 / 1,494 in 16 / 21 / 10 blocks. The satellite-only
models beat no change in every region with intervals that exclude zero
(`landsat_terrain_eco` minus no change: -0.129, -0.383, -0.433 m). Their edge over
the survey-based growth curve is small: -0.008, -0.041, -0.076 m for the
Landsat + terrain + climate + ecosystem model.

## Checks

- Scramble test (`reports/growth_sham_check.json`): shuffling the Landsat
  features between pixels, or replacing them with noise, returns the error to
  the constant-growth level (0.54 to 0.68 m). The skill comes from each pixel's
  own history.
- Inputs: terrain, climate and ecosystem without Landsat reach 0.404 / 0.538 /
  0.629 m. Landsat alone reaches 0.354 / 0.464 / 0.449 m. Adding site layers to
  Landsat changes little.
- Noise: the 2022 to 2023 pair gives a 30 m difference spread of 0.101 m, so
  noise alone would give a typical error near 0.08 m. The models sit at 0.35 to
  0.47 m, and mean growth of 0.4 to 0.8 m is well above the 0.199 m detection
  limit.

## Limits

- The claim is conditional on no large loss. The screen uses the LiDAR loss
  share, which comes from the label, so it describes growth given no
  disturbance, not what a utility would observe unscreened.
- CAL FIRE perimeters can be incomplete or generalized. Absence from the record
  does not show a cell was undisturbed. Logging is not in the record.
- East has few scored pixels and wide intervals.
- Regions adjoin the training regions. The 3 km buffer reduces but does not
  remove boundary correlation.
- This is net nine-year change from 2013. It says nothing about one-year skill.
- Which places will burn or be cut is not predicted here.
- Climate normals come in 4 km cells and can act as a place label. They added
  little once Landsat was present.

## Reproduce

```text
python scripts/ingest_landsat.py --region <study|west|east>
python scripts/ingest_site_sources.py --region <region>
python scripts/ingest_fire_perimeters.py --region <region>
python scripts/register_region_labels.py --region <west|east> --build-dir <label build>
python scripts/build_growth_table.py --region <region>
python scripts/train_growth_regions.py
python scripts/check_growth_sham.py
```

Label builds for west and east used `scripts/run_change.py --box` with 400 tiles
of 500 m each and the PDAL environment in `environment-lidar.yml`.
