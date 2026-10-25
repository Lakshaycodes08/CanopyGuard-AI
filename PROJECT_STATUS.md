# CanopyGuard-AI project status

Checked: 2026-10-25. GitHub issue, PR, and review states were checked today.
The current work is on `codex/stage2-terrain-paper`.
GitHub and research status can change after this snapshot; verify linked issues
and pull requests before relying on a closure claim.

## Decision

Phase 0 is **GO** on the exact northern Sonoma feasibility box, supported by
`reports/data_feasibility.md`. Phase 1 is **CONDITIONAL GO**, not complete:
the 2013-2022 label and growth-prior work has advanced, but the full
prospective feature, validation, and operational risk chain remains unproved.
The status in `reports/phase1_data_protocol.md` is the formal Phase 1 gate.

## Verified and open work

| Item | State | Evidence and limit |
| --- | --- | --- |
| Phase 0 six-gate feasibility | Completed and verified | `reports/data_feasibility.md` records GO for the exact study box. This is feasibility, not forecast validation. |
| PRs [#5](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/5), [#9](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/9), [#11](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/11), [#12](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/12), [#13](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/13) | Completed and merged | GitHub merge state checked. PR #13's wire exclusion is implemented; its preset review criterion failed and independent scientific assessment remains open. |
| PR [#16](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/16) | Merged 2026-10-25 | Satvik answered Q1-Q3 on issue #19 and approved the PR on 18 October with four conditions. PR #20 landed just before #16; the report confirms near-line and wire exclusions precede A; the manuscript places the all-forest result beside the screened result; the PR description was updated. Its remaining use of "co-primary" for the loss-on screen should be read with the explicit upper-bound qualification. |
| PR [#17](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/17) | Merged 2026-10-17 | Rehaan records author confirmation of band order and joint prediction, attributed to an email held outside the repo. The author record is now on main. |
| PR [#18](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/18) | Merged 2026-10-17 | The 2018-2023 point-cloud co-coverage report is on main; its reported area is not a reconciled G3 label area. |
| PR [#20](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/20) | Merged 2026-10-25 | Its all-forest sensitivity and revised manuscript are on main. |
| Issue [#8](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8) | Closed | G3 implementation and report are on main through PR #16. GitHub closure verified 2026-10-25. |
| Issue [#19](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/19) | Closed | Satvik's 18 October answers and formal approval are recorded. The four pre-merge conditions were checked against the merged report, manuscript, and PR description. The historical G3 JSON still records the earlier review state at its run time. GitHub closure verified 2026-10-25. |
| Issue [#15](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/15) | Closed | PR #18 reports 6.7 km2 usable canopy, none inside the study box. The 2026-10-25 owner decision retains it only as a possible small out-of-area check, pending 2018 epoch admission. GitHub closure verified 2026-10-25. |
| Issue [#14](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/14) | Open, labelled optional | Point-level wire filtering would improve corridor labels, but its issue text makes it optional for this paper. The `optional` GitHub label was applied 2026-10-25. |
| G1, 2022-2023 LiDAR noise floor | Measured, raw evidence absent locally | `MEMORY.md` records a pass on 284 seam tiles: shift 0.137 m, 10 m LoD95 0.235 m. The 0.054 spatial decay exponent qualifies interpretation as an offset field. Raw files remain with the team in Google Drive and have not been brought into this repository. |
| G2, ECHOSAT coverage | Completed and verified: PASS for coverage only | `reports/echosat_check.md` records full valid 2018-2023 coverage of the configured box. This does not validate year-to-year growth, band-year mapping, or use as a 2013 predictor. ECHOSAT is benchmark-only for this forecast. |
| G3, stage-one growth prior | Implemented and scientifically reviewed | `reports/growth_curve_check_2013-2022.md` reports the spatial median-prior gate PASS on both forest screens. The Chapman-Richards curve does not beat the median. Satvik approved its empirical A interpretation and manuscript caveats on 18 October. Persistent-forest visual audit remains incomplete. |
| Post hoc all-forest and objective checks | Completed and verified locally; not a gate | `reports/g3_posthoc_forest_sensitivity.md` shows an all-forest 2 km median gain of -0.062 m with interval crossing zero, versus -0.121 m after fire/Hansen screening. An intercept-only squared-error residual worsens MAE by +0.028 m. These findings qualify the paper's screened result and stage-two interpretation. |
| 2012 3DEP terrain on 10 m labels | Completed and verified locally | `data/interim/terrain_10m.parquet` has one complete row per 1,478,103 existing `cell_id` values. DVC and provenance sidecars record the source and hashes. The label CRS is EPSG:6339. The former 100 m config value was unused and corrected. |
| E4 ridge and E5 LightGBM stage-two gate | Completed and verified locally; gate rejected | `reports/stage2_residual_check_2013-2022.md` reports both FAIL on the frozen forest loss-OFF 2 km gate. Stage-one MAE is 1.256 m; ridge 1.336 m and LightGBM 1.309 m. The positive loss-ON sensitivity does not change the decision. |
| Manuscript | Draft, compiled locally | `paper/main.tex` presents screened G3 and stage-two results, the all-forest caveat, and a descriptive 18-class curve table. Satvik reviewed the G3 interpretation; broader publication review remains. |
| Sentinel-2, GEDI, ECHOSAT | Planned for their documented roles | Sentinel-2 observations after 2013 cannot predict the 2013-to-2022 outcome. GEDI is an independent height cross-check; ECHOSAT is a product benchmark. Neither is a stage-two predictor. |
| E8 ECHOSAT benchmark | Runner implemented, no height score | `reports/e8_alignment_protocol.md` pins the EPSG:32610 to EPSG:6339 operation and `reports/e8_benchmark_prereg.md` was pushed as `e660e92` before scoring. PR #17 is merged. The local branch has a DVC source stage, E8 scoring stage, report writer, and seven passing offline tests. The study-box ECHOSAT raster is absent locally and the available Python runtimes lack the required geospatial packages, so the benchmark has not run. |
| Release environment consistency | In progress | `environment.yml` is the canonical Python 3.11 environment and CI includes `pip check`. The shared local scratch environment lacks declared geospatial packages and has unrelated conflicts. Verify a clean install and passing `pip check` before a DOI release. Status update (2026-10-20): seven other DVC entries need rebuild or verification before a DOI release: six pipeline stages have dependency hashes predating later code changes (some also lack cached outputs), and the tracked interim label archive is missing from the local cache. |
| E6/E7/E9/E10 and span ranking | Rejected/superseded for this deadline | These ladder entries and operational span ranking are descoped from the current 31 October package. The old config ladder lists them as legacy plans; no implementation or validated result is claimed. |

## Research boundary

The present height-change result is a spatially blocked comparison on screened
LiDAR cells. It is not a validated future-year forecast, utility clearance
measurement, or safety certification. Approximate public power-line geometry
cannot supply conductor clearance. Persistent-forest screening, model
generalization, and a validated independent risk check need further evidence.

## Next action

Run the frozen E8 benchmark in the canonical Conda environment after the
configured ECHOSAT study-box raster is fetched. Inspect the generated JSON and
report before deciding whether to undertake a second study area. The G1 raw
files are being requested from the teammate. Issue #14 remains open and optional.
