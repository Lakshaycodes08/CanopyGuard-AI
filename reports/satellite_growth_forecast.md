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

## Finding 3: disturbance is only weakly predictable

Task: rank 90 m pixels by the chance of later disturbance, using predictors dated
before the cutoff, with a whole region held out (`reports/hazard_forecast.json`).
Two targets: LiDAR loss share of at least 0.3 (any cause), and at least half the
pixel inside a fire perimeter. AUC, where 0.5 is a coin flip:

| Target and region | Base rate | Ecosystem rate only | Landsat + terrain + ecosystem |
| --- | --- | --- | --- |
| Loss, study | 0.03 | 0.687 | 0.837 |
| Loss, west | 0.14 | 0.686 | 0.724 |
| Loss, east | 0.24 | 0.719 | 0.763 |
| Fire, study | 0.37 | 0.792 | 0.906 |
| Fire, west | 0.44 | 0.664 | 0.694 |
| Fire, east | 0.77 | 0.452 | 0.448 |

- Loss: the satellite model improves on the ecosystem rate in all three regions
  (AUC gain +0.150, +0.038, +0.044; block-bootstrap intervals exclude zero). The
  gain is small in west and east. The top 10 percent of ranked pixels hold 17 to
  40 percent of loss pixels, against 10 percent for random ranking.
- Fire: not usable. AUC ranges from 0.42 to 0.92 across regions and feature
  sets, and falls below 0.5 in the east, where 77 percent of pixels are inside a
  perimeter. Fire footprints are large blobs, three regions cannot separate
  fire geography from fire risk, and weather and ignition are not in the
  predictors. No fire-prediction claim should be made from this test.
- Adding 2013 LiDAR height to the predictors did not help the loss ranking in the
  west or east.

## Finding 4: line segments

The county transmission layer has 41 line features in the study box, 8 in the
west box and 14 in the east box. It has no tower points, so lines were cut into
pieces of about 300 m. These are working segments, not engineered spans. Each
segment's corridor is the set of 30 m pixels within 60 m of it that hold canopy
(canopy share at least 0.3). Predictions for a region come from models trained
on the other two regions (`reports/span_ranking.json`, pooled over regions).

Segments with enough pixels at 60 m: growth, 107 (96 study, 11 west, 0 east);
loss, 285 (211 study, 22 west, 52 east). Most corridor canopy sits inside fire
perimeters, so the unburned-growth question has few segments outside the study
box.

Share of the segments with the most observed change that the top 20 percent of
predicted line length captures (random ranking gives 0.20):

| Ranking by | Growth (107 segments) | Loss (285 segments) |
| --- | --- | --- |
| Satellite, Landsat + terrain + ecosystem | 0.32 | 0.47 |
| Satellite, Landsat + terrain + climate + ecosystem | 0.32 | 0.39 |
| Ecosystem type only | 0.18 | 0.32 |
| Survey height and ecosystem growth curve (uses 2013 LiDAR) | 0.23 | not run |
| Tallest segments first (uses 2013 LiDAR) | 0.27 | 0.47 |
| Satellite + survey height (comparison, uses 2013 LiDAR) | 0.32 | 0.41 |

- Rank correlation of predicted and observed corridor growth is +0.52 for the
  satellite model, against -0.13 for ecosystem type, +0.14 for the survey growth
  curve and +0.09 for tallest first.
- The satellite model sits above random in both tasks, but its edge over the
  simple alternatives is not established: the paired block-bootstrap intervals
  include zero for nearly all comparisons. The exception is growth at 100 m
  corridors against ecosystem type, +0.23 recall at 20 percent (interval
  +0.05 to +0.37).
- Tallest-first ranking, the common practice, matches the satellite model on
  loss and trails it on growth. It does not need a survey to be refuted: it
  simply carries no growth signal here.
- Predicted loss chances are lower than observed loss shares in the east, so the
  numbers are for ranking, not calibrated probabilities.
- Maps: `reports/figures/span_forecast_growth.png` and
  `reports/figures/span_forecast_loss.png`.

The growth and loss rankings use only about 100 and 300 segments, mostly from
one region. Treat these as early evidence.

## Finding 5: the growth result holds with no LiDAR in the screen

The screen in Finding 2 used the LiDAR loss share, which comes from the answer
key. A satellite-only screen keeps rows with no fire perimeter dated between the
surveys and a persistent Landsat NBR loss below the published dNBR level of
0.10 (mean of the last two summers, 2021 and 2022, against the 2011 to 2013
baseline; the last window ends the day before the 2022 survey). The 0.10 level
is a literature value and was not tuned on the labels.

Typical error in metres at 90 m, region held out (`undisturbed_satellite`,
`reports/growth_region_transfer.json`):

| Method | Study | West | East |
| --- | --- | --- | --- |
| No change | 0.505 | 0.871 | 0.916 |
| Constant average growth | 0.485 | 0.712 | 0.715 |
| Growth by ecosystem type | 0.426 | 0.666 | 0.646 |
| Survey height and ecosystem growth curve (uses 2013 LiDAR) | 0.412 | 0.647 | 0.639 |
| Satellite only, Landsat | 0.391 | 0.628 | 0.555 |
| Satellite only, Landsat + terrain + ecosystem | 0.389 | 0.604 | 0.545 |

- Scored pixels: 4,399 / 3,621 / 1,240 in 16 / 21 / 10 blocks.
- The satellite-only model beats no change by 0.116, 0.267 and 0.371 m, and the
  survey-based curve by 0.023, 0.043 and 0.094 m. All six block-bootstrap
  intervals exclude zero.
- Errors are a little higher than with the LiDAR screen (0.351 / 0.453 / 0.470
  for the same model), because the satellite flag leaves more partial loss in
  the kept rows. The ordering of methods is the same.
- At 300 m the gain over no change holds in all three regions; the edge over the
  survey curve is not resolved in two of them.

Screen agreement (`reports/screen_crosscheck.json`, 90 m): the continuous NBR
loss ranks LiDAR-measured loss rows with AUC 0.842, 0.849 and 0.916 (study,
west, east). Kept shares are 0.37, 0.43 and 0.13 for the satellite screen, and
0.43, 0.47 and 0.15 for the LiDAR screen. The 0.10 flag is more lenient than the
LiDAR screen on small partial losses: among fire-free rows it flags 5 to 16
percent while LiDAR loss share above 0.1 covers 32 to 53 percent, so its recall
of those rows is low (0.03 to 0.13).

One Landsat 8 file (`LC08_L2SP_045033_20220721_02_T1`, red band) is corrupt on
the server and was skipped in all three regions. The skip is recorded in the
composite files.

ECHOSAT cross-check (`reports/screen_crosscheck.json`, 90 m rows): ECHOSAT
height maps for 2018 and 2022 were read from the Earth Engine copy of the
product, one 90 m cell per row, as the share of 10 m pixels whose height fell by
5 m or more. A row counts as abrupt loss when that share is at least 0.10. It is
an independent, modeled product used only to check the screens.

| Region | Screen | Kept rows | Removed rows |
| --- | --- | --- | --- |
| Study | Satellite (fire + Landsat) | 0.2 percent | 1.7 percent |
| Study | LiDAR loss share | 0.2 percent | 1.8 percent |
| West | Satellite (fire + Landsat) | 0.1 percent | 6.2 percent |
| West | LiDAR loss share | 0.0 percent | 6.8 percent |
| East | Satellite (fire + Landsat) | 0.1 percent | 4.2 percent |
| East | LiDAR loss share | 0.1 percent | 4.3 percent |

Share of rows with ECHOSAT abrupt loss. The rows both screens keep are almost
free of it, and the rows they remove carry 8 to 60 times more. Fire perimeters
alone leave 0.4 percent (study), 0.2 percent (west) and 0.3 percent (east) of
kept rows with ECHOSAT abrupt loss, so the Landsat step removes some disturbance
that the fire records miss.

Limits of this check: ECHOSAT starts in 2018, so it cannot confirm removals of
earlier events such as the 2017 Tubbs fire or earlier cuts; the rates are small
because most removed rows were disturbed before 2018. ECHOSAT is a modeled
product whose maps all draw on imagery through 2024, so it is a cross-check, not
ground truth, and it is never a predictor or a screen here.

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

- The claim is conditional on no large disturbance. Finding 2 screens with the
  LiDAR loss share, which comes from the label; Finding 5 repeats it with a
  satellite and fire-record screen and the result holds. Neither describes what
  a utility would observe unscreened.
- CAL FIRE perimeters can be incomplete or generalized. Absence from the record
  does not show a cell was undisturbed. Logging is not in the record.
- East has few scored pixels and wide intervals.
- Regions adjoin the training regions. The 3 km buffer reduces but does not
  remove boundary correlation.
- This is net nine-year change from 2013. It says nothing about one-year skill.
- Loss is ranked only weakly and fire not at all; see Finding 3.
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
