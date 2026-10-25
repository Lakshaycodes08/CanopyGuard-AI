# CanopyGuard-AI: status and direction (brief for review)

Date: 2026-10-25. Work branch: `feat/satellite-growth-forecast`, local only.
This is a research prioritisation study, not a clearance or safety determination.

## 1. The question

Can data available before a cutoff date (satellite history, terrain, climate
normals, an ecosystem map) forecast canopy growth without an airborne survey as
an input? Airborne LiDAR is used only as the answer key and the grader.

## 2. The answer so far, in plain words

- **Steady growth: yes.** In forest that was not burned or cut, a model using
  only data dated before 2013-09-27 forecasts the 2013 to 2022 height change in
  regions it never saw. It matches or slightly beats methods that need a LiDAR
  survey.
- **Disturbance (fire, cuts): mostly no.** A plain regression on all pixels
  learns where fires burned, not growth, and fails on new regions. Ranking
  loss shows a small real signal. Fire cannot be forecast from this data.

## 3. Key numbers (90 m blocks, typical error in metres, region held out)

Screen without LiDAR: no fire perimeter between the surveys, and persistent
Landsat NBR loss below 0.10.

| Method | Study | West | East |
| --- | --- | --- | --- |
| No change | 0.505 | 0.871 | 0.916 |
| Growth by ecosystem type | 0.426 | 0.666 | 0.646 |
| Survey height and ecosystem growth curve (uses 2013 LiDAR) | 0.412 | 0.647 | 0.639 |
| **Satellite only** | **0.389** | **0.604** | **0.545** |

- Satellite minus ecosystem-type growth: -0.037, -0.062, -0.101 m. Satellite
  minus survey curve: -0.023, -0.043, -0.094 m. All six block-bootstrap 95
  percent intervals exclude zero. Scored blocks: 16, 21, 10.
- The edge over the simple baselines is small: 0.02 to 0.10 m on growth of
  0.4 to 0.8 m over nine years.
- Scrambling the satellite inputs returns the error to the constant-growth
  level (0.54 to 0.68 m), so the skill comes from each pixel's own history.
- Loss ranking AUC: 0.84, 0.72, 0.76 against 0.69, 0.69, 0.72 for ecosystem
  type alone. Fire: no stable result.
- Screen cross-check (ECHOSAT height drop, 2018 on): kept rows show abrupt loss
  in 0.1 to 0.2 percent of rows, removed rows in 1.7 to 6.2 percent.

## 4. What is done

1. LiDAR change labels 2013 to 2022 for three regions: 1,478,103 (study),
   923,611 (west) and 965,770 (east) valid 10 m cells.
2. Predictors dated before the cutoff: Landsat 2001 to 2013, satellite-radar
   terrain, TerraClimate 1981 to 2010 normals, GAP/LANDFIRE 2011 ecosystems.
   No LiDAR, no GEDI. The Sonoma vegetation map is a comparison only, because
   its attributes are partly LiDAR-derived.
3. Tests: leave-one-region-out with a 3 km buffer, paired block bootstrap,
   scramble test, LiDAR noise-floor check.
4. Disturbance screens built without LiDAR (fire perimeters, Landsat change
   after the cutoff) and checked against ECHOSAT.
5. Early line-segment ranking on the county transmission layer.
6. Scripted, config-driven, seeded pipeline with provenance sidecars; 561
   tests pass. Nothing has been pushed.

## 5. How it fits the existing work (PR #20)

- Same ground truth, different question. PR #20 works at 10 m inside one
  region, with 2013 LiDAR height, terrain and map class as inputs. Its stage-two
  models do not beat the ecosystem-type median increment in fire and
  Hansen-screened forest (+0.080 and +0.052 m worse). That median beats no
  change by 0.121 m.
- This work shows the same two facts at 90 m: the type median is a strong
  baseline, and survey height adds little. What is new is that satellite
  history beats the type median when the region is new.
- Open overlaps: both lines edit `reports/claims_log.md` and
  `reports/research_design.md`; the research question and README still treat
  LiDAR at t0 as a model input; PR #20 uses a Hansen loss screen that this work
  has not added yet.

## 6. Reserved test (data kept out of training)

- 2023 LiDAR has never been used: not in labels, screens, features or models.
- 2013 and 2023 overlap on only about 22 km2 (89 tiles; 47 admitted, 98,509
  cells), spread over seven small clusters. Those tiles and a 3 km buffer are
  excluded from every training and scoring run. Models are scored on them once,
  against 2013 to 2023 change, with predictions also stretched by the interval
  ratio (10.01 to 8.96 years).
- The 2022 to 2023 pair is used only for the noise floor. One year of growth is
  below the LiDAR noise per cell, so it cannot test skill.
- Status: labels built; satellite data for the seven clusters is downloading.
  Result: pending.

## 7. To do

1. Run the reserved test and record it as is.
2. Reconcile with PR #20: same-cell comparison, add the Hansen screen, merge the
   documents.
3. Add a fourth region inside Sonoma County (the south box), because the 2013
   survey covers only Sonoma.
4. Thesis text and figures from `reports/satellite_growth_forecast.md`.
5. Optional: a GPU patch network as an extension, only after 1 to 4.

## 8. Limits to keep in view

- Net nine-year change from 2013, not a one-year forecast.
- Conditional on no large disturbance; the unscreened case is not solved.
- Fire perimeters can be incomplete, and logging is not in the record.
- Regions are neighbours in one county; east has only 1,240 scored 90 m cells in 10 spatial blocks.
- Line segments are cut from approximate geometry with no towers or conductors.
- ECHOSAT is a modeled product and cannot see events before 2018.

## 9. Decision requested

- **A (recommended).** Keep the direction. Satellite-only growth is the main
  contribution. LiDAR-at-t0 models become the upper-bound comparison.
  Disturbance stays a separate, weaker part.
- **B.** Pivot to disturbance and loss ranking as the main target. It matters
  more to utilities, but the evidence is weaker.
- **C.** Keep LiDAR at t0 as the main design (the PR #20 line) and treat
  satellite-only as a side experiment.

Please also confirm the claim scope: net nine-year change, conditional on no
large disturbance, in unseen regions of one county.
