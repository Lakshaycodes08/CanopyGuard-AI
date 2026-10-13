# Wire and tower label check, 2013-2022 (issue 6)

Status: implemented, tested and run; raw points inspected for a sample of 120 cells; not independently reviewed; imagery not inspected. This is a research label quality check, not a clearance or safety assessment.

## Inputs
- Raw archive `labels_2013-2022.npz`, SHA-256 `dc91f03b4f067a54a6666fc15cfdf6b86dc368a1d97e44555fb762515ab10763` (matches `label_quality_2013-2022.md`).
- The numbers below were computed from the raw archive using the documented overlap rule (highest minimum coverage, then higher total coverage, then lower tile ID). The rebuild gives 1,478,301 valid rows, 1,478,103 unique cells and 198 disputed cells, all matching `label_quality_2013-2022.md`. This leaves 1,477,905 cells. `configs/lidar.yaml` points the script at the unique archive, which uses its `overlap_disputed` flag; the raw route is the fallback when that flag is absent.
- CEC transmission lines: 41 LineString features (PG&E, overhead), 364 km, from the California Energy Commission layer (Sonoma County copy), queried with the study box. Reprojected to EPSG:6339. Digitised from imagery, so positions are approximate. No tower points.

## Rules (fixed before any rate was computed)
- Isolated tall cell: 1 m maximum at least 10 m and median of the 8 neighbours' maximum at most 3 m (at least 4 valid neighbours). Wire-like subset: also maximum minus 95th percentile at least 5 m.
- Each epoch separately. Eligible cell: finite maximum, enough neighbours, valid fraction at least 0.5. Eligible cells: 1,473,936.
- Near band 0-30 m (primary); 30-100 m (secondary). Controls: more than 250 m from any line, same tile, stratified by tile, starting canopy_share bin (0.1) and valid-fraction bin. Matching avoids height maxima on purpose.
- Estimate: observed near-line flags divided by expected flags from the matched control rate. Tile bootstrap, 2000 draws, seed 42, 95% interval.
- Pass: upper bound of the ratio at most 1.25 in the 0-30 m band, in both epochs.
- The thresholds are proposals, not literature values.

## Result: fail under the pre-set rule
| Epoch | Flag | Near flagged | Observed | Expected | Ratio (95% CI) |
|---|---|---:|---:|---:|---|
| 2013 | isolated | 904 | 797 | 614.8 | 1.30 (0.93-1.78) |
| 2013 | wire-like | 334 | 325 | 115.1 | 2.82 (1.97-4.12) |
| 2022 | isolated | 1193 | 964 | 636.9 | 1.51 (1.14-2.02) |
| 2022 | wire-like | 514 | 436 | 91.1 | 4.79 (3.49-6.77) |

Denominators: near 92,059 cells, controls 811,358. The 2013 isolated interval includes 1 but its upper bound exceeds 1.25, so it fails the rule without showing a clear excess. The 30-100 m band shows no excess (ratios 0.92 to 1.09). Raw isolated rate within 10 m of a line: 1.9% (2013) and 2.6% (2022); beyond 10 m about 0.3-0.7%, equal to background.

## Checks
- Placebo, lines shifted 400 m in four directions, cells within 100 m of real lines excluded: isolated ratios 0.57-0.89, wire-like 0.47-1.03. No excess, so the estimator does not create the effect. See `reports/wire_check_2013-2022/verification.json`.
- Post hoc sensitivity at a 15 m height threshold (not the pass rule): isolated ratio 2.84 (2013) and 2.83 (2022); wire-like 6.78 and 10.66.
- Persistence: 477 of 904 near-line cells flagged in 2013 are also flagged in 2022, similar to controls (1,779 of 3,782). Not discriminating.

## Raw point inspection (120 cells)
Sample: 30 near-line and 30 control cells for each flagged epoch, read for both epochs from the public 3DEP store. Near-line cells are the ones with the largest maximum-minus-p95 gap, so they are the most spike-like and not a random draw. Do not read the shares below as the share of all 1,620 flagged near-line cells. 233 of 240 cell-epoch reads succeeded; 7 failed with a read error and were not retried.

- Wire (class 14) and tower (class 15) points: zero in every cell, both epochs. Classes present: 2013 = 1, 2, 5, 6, 7; 2022 = 1, 2, 7, 18. The source classification does not label wires or towers, so a class filter cannot remove them. The pipeline keeps class 1 (unclassified).
- 2013, epoch matched to flag: tallest return is class 1 in 27 of 29 near-line cells; class 5 (high vegetation) in 20 of 27 control cells. Fewer than 10 points beneath the tallest return within 2 m: 24 of 29 near-line (83%) vs 4 of 27 control (15%). Median points beneath: 0 vs 71. Median tallest height 22.7 m vs 12.3 m.
- 2022, epoch matched to flag: 12 of 30 near-line (40%) are thin vs 6 of 30 control (20%); median points beneath 21.5 vs 166. Four near-line and three control tallest returns are class 18 (high noise), which the pipeline drops; use `second_highest_m` for those. Most 2022 near-line spikes are not clearly thin objects; many are tall trees with dense crowns. A tall tree at a corridor edge is research-relevant signal, not an artifact.
- Near-line spikes are 20-45 m tall (median 26.6 m, 90th percentile 40.5 m), consistent with towers, poles or wires. Imagery was not checked.

Reading: strong evidence that the 2013 near-line excess is mostly thin unclassified objects (likely wires, poles or towers); weaker and mixed for 2022. Not proven to be wires. The "fewer than 10 points" cutoff was set while reading results and is descriptive only.

## Effect on the labels
Cells within 30 m of a line: 92,141. Flagged in either epoch: 1,620 (1.8% of near-line cells, 0.11% of all analysed cells). Mean change is unaffected (mean absolute mean_change near lines 1.591 with and without them). Flagged cells are more often in the tails of p95_change (21% with absolute change of 10 m or more vs 7% for unflagged near-line cells). Only 153 of 5,317 near-line cells with absolute max_change of 10 m or more are flagged, so masking will not remove most large near-line changes. Proposed mask: `reports/wire_check_2013-2022/proposed_mask_near_line_flagged.csv` (1,620 cell IDs).

## Limits
Approximate horizontal line geometry only; no tower points in the CEC file; no conductor height and no clearance inference; sample of 120 cells chosen for spike-likeness; thin cutoff set after seeing results; imagery not inspected; 7 read errors not retried; thresholds are proposals.

## Reproduce
1. Put the line file at `data/interim/cec/cec_lines_study_box.geojson` (not committed).
2. `python scripts/check_wire_labels.py` writes results, suspects, mask and figures to `data/processed/wire_check/`.
3. `python scripts/verify_wire_check.py` writes `verification.json` there.
4. `python scripts/inspect_wire_points.py` (needs python-pdal and network) writes `suspect_points_summary.csv` there.
5. Committed evidence copies are in `reports/wire_check_2013-2022/`.

## Decision needed
Add a `wire_suspect` flag for the 1,620 cells and exclude them from near-line maximum and p95 analyses (recommended), or filter thin returns at point level and rebuild corridor tiles. Either way, an independent reviewer should confirm before any model uses these labels.
